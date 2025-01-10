Storage proof network
=====================

Authors: Codex Team

In this document we explore a design for an off-chain network for validating
[storage proofs][1]. Instead of checking each storage proof in a smart contract
on-chain, we let the proof network check these proofs. Only when a proof is
missing we go on-chain to enact slashing. The main goal of this exercise is to
reduce the costs of submitting and validating proofs, which has shown to be a
limiting factor for the profitability of storage providers and the scaling of
the storage network, even when deploying on a [rollup][2] or [sidechain][3].

[1]: proof-erasure-coding.md
[2]: ../evaluations/rollups.md
[3]: ../evaluations/sidechains.md

Overview
--------

The main idea is that validators in the network sign off on messages containing
correct storage proofs, and on messages that correctly indicate that a proof is
missing. These validators deposit a stake on-chain. We consider a message to be
validated by the network when a subset of the validators representing > 2/3 of
the total network stake have signed off on it. The assumption here is that less
than 1/3 of the validators are byzantine, meaning that the rest is online and
following protocol.

Roles in the network are:

- provers: they are the storage providers that submit storage proofs
- validators: they sign off on submitted proofs and missed proofs
- watchers: they monitor for missing proofs, and trigger slashing on-chain

They are all connected to the same peer-to-peer gossipsub network in which they
exchange messsages. The provers and watchers also monitor the on-chain
marketplace to check when storage proofs are required.


        prover                                              validator

            prover  <--------->  gossipsub  <-------------->  validator

        prover  ^                    |                      validator
                 \                   |
                  \                  |
                   \                 v   watcher
                    \
                     \             watcher
                      \
                       \            ^   watcher
                        \           |
                         \          |
                          \         |
                           \        v

                           marketplace
                           (on-chain)

Messages
--------

The messages that are exchanged over the gossipsub network are:

- `SubmitProof(slot id, period, inputs, proof)`
- `ProofSigned(slot id, period, inputs, signature)`
- `ProofValidated(slot id, period, inputs, combined signature)`
- `SubmitMissed(slot id, period, inputs)`
- `MissedSigned(slot id, period, inputs, signature)`

A *slot id* parameters refers to a [slot in a storage request][4] on the
marketplace. It uniquely identifies the data for which a storage proof is
required. The *period* refers to a [time interval][5] in which the storage proof
should be submitted. By *proof* we mean a [zero-knowledge proof][5], and by
*inputs* we mean its public inputs. A *signature* is a BLS validator signature,
and a *combined signature* is a BLS signature that is a combination of multiple
validator signatures.

#### SubmitProof ####

A prover broadcasts a `SubmitProof` message to indicate to the network that it
calculated a storage proof as required by the marketplace.

#### ProofSigned ####

A validator broadcasts a `ProofSigned` message in response to a `SubmitProof`
message. It only responds with `ProofSigned` after verifying the correctness of
the zero knowledge *proof* w.r.t. its public *inputs*, and checking that the
time *period* has not ended yet.

#### ProofValidated ####

A prover broadcasts `ProofValidated` after it collected enough `ProofSigned`
messages from the validators. It combines the BLS *signatures* that it received
into a single *combined signature* which represents > 2/3 stake of the network.

#### SubmitMissed ####

A watcher broadcasts a `SubmitMissed` when it notices that a required proof was
not submitted.

#### MissedSigned ####

A validator broadcasts `MissedSigned` only when the *period* has ended, and the
validator did not previously broadcast a `ProofSigned` for the same *slot id*,
*period* and *inputs*.

[4]: marketplace.md
[5]: https://github.com/codex-storage/codex-storage-proofs-circuits#circuit

Flows
-------

### Successfull proof submission and validation ###

Provers monitor the on-chain marketplace to check in which periods they need to
provide a storage proof. When a prover sees that a proof is required for a slot
in the current *period*, it gathers public *inputs* for the slot, including the
random challenge and calculates a zero-knowledge storage *proof*. The prover
then broadcasts `SubmitProof(slot id, period, inputs, proof)`:

                                                             validator
                      SubmitProof
            prover  --------------------------------------->  validator

                                                            validator

Upon receiving a `SubmitProof` message a validator checks that the *period*
hasn't ended yet and that the *proof* is correct w.r.t. to the *inputs*. If that
is all in order it will sign and broadcast a `ProofSigned(slot id, period,
inputs, signature)` message:


                                                             validator
                                            ProofSigned
            prover  <---------------------------------------  validator

                                                            validator

Provers listen for these `ProofSigned` messages from the validators, and once
they accumulated enough *signature*s from validators to represent > 2/3 stake,
they create a *combined signature* and broadcast `ProofValidated(slot id,
period, inputs, combined signature)`:

                      ProofValidated
            prover  ------------------.
                                      |
                                      |
                                      v  watcher

                                   watcher

                                        watcher

### Missing proofs ###

Watchers monitor the on-chain marketplace to check which slots require a storage
proof to be submitted and what the public *inputs* for the proof are. For each
required proof they then monitor the gossipsub network for `ProofValidated`
messages. If they do not observe a `ProofValidated` message that is signed by >
2/3 stake before the end of the period with the expected *slot id*, *period* and
*inputs* parameters, then they will broadcast a `SubmitMissed(slot id, period,
inputs)` message.

                                                            validator

                                     .-------------------->  validator
                                     |
                                     |                     validator
                                     |
                        SubmitMissed |
                                     |

                                   watcher

Upon receiving a `SubmitMissed(slot id, period, inputs)` message a validator
checks that the *period* has ended and that it hasn't already sent out a
`ProofSigned` message for the *slot id*, *period* and *inputs*.  If it indeed
did not, then it will sign and broadcast a `MissedSigned(slot id, period,
inputs, signature)`.

                                                            validator
                                             MissedSigned
                                     .---------------------  validator
                                     |
                                     |                     validator
                                     |
                                     |
                                     v

                                   watcher

When the watcher receives enough *signature*s to represent > 2/3 stake it can
combine these signatures into a single *combined signature*. The watcher can
then submit *slot id*, *period*, *inputs* and *combined signature* to the
marketplace.

The marketplace will then verify the correctness of *inputs* for the *slot id*
and *period*, and checks that the *combined signature* is representative for >
2/3 stake. If these conditions are met, it will then slash the storage provider
collateral and reward the watcher.

### Faulty proofs ###

The storage proofs that a prover submits can be faulty for a number of reasons:

1. The zero knowledge *proof* is incorrect
2. The submitted *period* is not the current time period
3. The public *inputs* to the proof do not match the values from the on-chain
   marketplace

Faults 1 and 2 are caught by the validators. Correct validators will not sign
off on invalid zero-knowledge *proofs*, or on a *period* that is not the current
time period. This means that it is not possible to construct a `ProofValidated`
message with a *combined signature* representing > 2/3 stake. Watchers and
Validators are now free to treat the proof as missing, and go through the same
flow that we described in the previous section.

Fault 3 is caught by the watchers and the on-chain marketplace. Watchers will
look for a `ProofValidated` that has the same *inputs* as specified by the
marketplace. If it doesn't find it because the prover broadcast a
`ProofValidated` with a different value for *inputs*, then it will treat the proof as missing, and go through the same flow as in the previous section.

Consensus
---------

The core of our design consists of the fact that correct validators either sign
off on a `ProofSigned` message or on a `MissedSigned` message, but never on
both. We then use a light form of consensus by combining signatures of
validators representing > 2/3 stake. Because we assume that there are < 1/3
stake byzantine validators, it is always possible to either get enough
signatures to validate a correct proof that was submitted on time, or get enough
signatures to sign off on a missed or faulty proof.

There is one scenario in which consensus might not be reached. When a proof is
submitted at the end of its time period, and it reached some of the correct
validators before the period ends, and some of the correct validators after the
period ends. In this scenario it can occur that it's not possible to get enough
signatures to validate the proof, and not enough signatures to sign off on a
missed proof.

We argue that is not a problematic scenario for our storage proof network. The
prover did provide a correct proof to at least one correct validator, meaning
that it is still storing the data that it is supposed to. Not being able to
slash the prover in this case is therefore ok.

Staking
-------

It can be expensive to calculate the amount of stake associated with a combined
BLS signature on-chain. Because any combination that represents > 2/3 stake is
valid, there can be many different valid combinations. If we have to calculate
the amount of stake every time that a watcher submits a combined signature that
signals that a proof was missed, then the gas fees would be prohibitive.

So instead we expect there to be pre-calculated combined public keys that
represent > 2/3 stake majorities. The gas costs for validating the stake that
these combined public keys represent can be borne by the validators when they
put down their stake.

The tokens that validators deposit as stake can be used to keep them honest.
Should a validator sign off on an invalid proof, then the invalid proof and the
signature can be used to prove on-chain that the validator misbehaved. Their
stake, or a part thereof, can then be burned as a disincentive for misbehaving.

Pros and cons
-------------

There are a couple of advantages to using a very light form of consensus. The
validators do not need to communicate amongst themselves, so we can forego the
three rounds of communication inherent to Byzantine Fault Tolerant consensus
algorithms. This leads to less communication overhead and lower latency.

Our design also allows validators to operate nearly stateless. They only need to
keep track of which proofs they themselves signed off on for the current period
and one or two previous periods, depending on how much time we want to allow for
watchers to notice missing proofs and submit `MissedSigned` messages.

In exchange for these advantages we have a drawback as well. The number of
validators is by necessity fairly small (in the order of < 100 validators)
because each prover needs to send messages to and receive responses from about
2/3 of the validators. Measures can be taken to increase the decentralization of
the validators. We could for example introduce epochs in which some validators
are chosen from a larger set of potential validators, but that comes at the
expense of added complexity.
