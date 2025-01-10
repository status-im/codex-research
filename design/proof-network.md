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

The main idea is that validators in the network sign off on blocks of
transactions. Transactions either contain a storage proof, or indicate that a
storage proof is missing. These validators deposit stake on-chain that allows
them to participate in a staked consensus protocol. This consensus protocol
ensures that transactions are only validated when a subset of the validators
representing > 2/3 of the total network stake have signed off on it. The
assumption here is that less than 1/3 of the validators are byzantine, meaning
that the rest is online and following protocol.

Roles in the network are:

- storage providers: they submit storage proofs
- validators: they keep track of submitted and missed proofs, and trigger
  slashing on-chain

The validators form a consensus network that allows them to agree on blocks of
transactions. Storage providers submit transactions containing a storage proof
to one of the validators, which includes it in a block of transactions.
Validators also monitor the on-chain marketplace to check when storage proofs
are missed.

                                                 consensus network

                                       --------------------------------------
     storage providers                 |                                    |
                                       |               validator            |
    ---------------------              |                ^    ^              |
    |                   |              |               /      \             |
    |    provider       |              |              /        \            |
    |                                                v          v           |
    |      provider  <--------------------->  validator <----> validator    |
    |                                                ^          ^           |
    |  provider         |              |              \        /            |
    |                   |              |               \      /             |
    ---------------------              |                v    v              |
           ^                           |               validator            |
           |                           |                                    |
           |                           --------------------------------------
           |                                          ^
           |                                          |
           |             ethereum                     |
           |                                          |
           |        ------------------                |
           |        |                |                |
           \------- |  marketplace   | <--------------/
                    |                |
                    ------------------

Transactions
------------

The types of transactions that can be included in blocks are:

- `StorageProof(slot id, period, inputs, proof)`
- `MissingProof(slot id, period, inputs)`

Each transaction is signed by its sender. A *slot id* parameters refers to a
[slot in a storage request][4] on the marketplace. It uniquely identifies the
data for which a storage proof is required. The *period* refers to a [time
interval][5] in which the storage proof should be submitted. By *proof* we mean
a [zero-knowledge proof][5], and by *inputs* we mean its public inputs.

#### StorageProof ####

A storage provider sends a `StorageProof` transaction to a validator to indicate
to the network that it calculated a storage proof as required by the
marketplace. This validator includes it in its next block.

#### MissingProof ####

A validator includes a `MissingProof` transaction in its next block when it
notices that a required storage proof was not submitted.

[4]: marketplace.md
[5]: https://github.com/codex-storage/codex-storage-proofs-circuits#circuit

Flows
-------

### Successfull proof submission ###

Storage providers monitor the on-chain marketplace to check in which periods
they need to provide a storage proof. When a provider sees that a proof is
required for a slot in the current *period*, it gathers public *inputs* for the
slot, including the random challenge and calculates a zero-knowledge storage
*proof*. The provider then submits `StorageProof(slot id, period, inputs,
proof)` to a single validator.


                       StorageProof
    storage provider  --------------------------------------->  validator


The validator will include the transaction in the next block that it proposes to
the consensus network. When the proposed block is sequenced by the consensus
network, the validator will return an inclusion proof to the provider. This is a
proof that the transaction was included in a block, and that the consensus
network included the block.


                                              inclusion proof
    storage provider  <---------------------------------------  validator


This inclusion proof doesn't need to be succinct, and can for example consist of
a record of the messages that were exchanged between validators as part of the
consensus protocol.

Notice that validators do not check the correctness of `StorageProof`
transactions prior to including them in blocks. In this design sequencing and
evaluation of transactions are separated. First, the validators reach consensus
on a sequence of blocks of transactions. Then, each of the validators evaluates
these transactions in order.

When evaluating a `StorageProof` transaction a validator checks that it was
submitted within the *period* and that the *proof* is correct w.r.t. to the
*inputs*. If that is all in order then it updates its internal accounting to
reflect that the proof was submitted and correct.

### Missing proofs ###

Validators monitor the on-chain marketplace to check which slots require a
storage proof to be submitted and what the public *inputs* for the proof are.
For each required proof they check at the end of its *period* whether that proof
was submitted and correct. If they did not receive a correct proof then they
will add a `MissingProof(slot id, period, inputs)` transaction to the next
block.

The `MissingProof` transactions are sequenced by the consensus algorithm. They
are then evaluated by each validator. They will note the first `MissingProof`
transaction that correctly notices a missing proof, and allow the sender of that
first transaction to go on-chain to mark the proof as missing.

The validator that sent the first `MissingProof` transaction for a missing proof
can now request BLS signatures from the other validators to enact on-chain
slashing of the storage provider for missing a proof. When the validator
receives enough signatures to represent > 2/3 stake it can combine these
signatures into a single combined BLS signature. The validator can then submit
*slot id*, *period*, *inputs* and the combined signature to the marketplace.

The marketplace will then verify the correctness of *inputs* for the *slot id*
and *period*, and checks that the combined signature is representative for > 2/3
stake. If these conditions are met, it will then slash the storage provider
collateral and reward the validator.

### Faulty proofs ###

The storage proofs that a storage provider submits can be faulty for a number of
reasons:

1. The zero knowledge *proof* is incorrect
2. The submitted *period* is not the current time period
3. The public *inputs* to the proof do not match the values from the on-chain
   marketplace

Faults 1 and 2 are caught by the validators. Validators check the zero-knowledge
*proof*, and that the *period* is the current time period when evaluating a
`StorageProof` transaction. If these are incorrect then they ignore the
transaction, effectively treating the proof as missing. Validators now go
through the same flow that we described in the previous section.

Fault 3 is caught by the validators and the on-chain marketplace. Validators
will look for a correct `StorageProof` transaction that has the same *inputs* as
specified by the marketplace. If it doesn't find it because the storage provider
submitted a `StorageProof` transaction with a different value for *inputs*, then
it will treat the proof as missing, and go through the same flow as in the
previous section.

Consensus
---------

Our design depends on a consensus algorithm between validators. This can be any
byzantine-fault-tolerant consensus algorithm for sequencing transactions. The
[Mysticeti][6] algorithm seems to be particularly suited because it is highly
performant.

The consensus algorithm is only used to sequence transactions. Evaluation of the
transactions is done after sequencing. This means that storage proofs can be
checked in parallel, which allows validators to scale up and support a large
storage network that produces many proofs.

[6]: https://arxiv.org/pdf/2310.14821

Staking
-------

The marketplace smart contract only slashes a storage provider when there is a
combined BLS signature that represents > 2/3 stake.

It can be expensive to calculate the amount of stake associated with a combined
BLS signature on-chain. Because any combination that represents > 2/3 stake is
valid, there can be many different valid combinations. If we have to calculate
the amount of stake every time that a validator submits a combined signature
that signals that a proof was missed, then the gas fees would be prohibitive.

So instead we expect there to be pre-calculated combined public keys that
represent > 2/3 stake majorities. The gas costs for validating the stake that
these combined public keys represent can be borne by the validators when they
put down their stake.

Pros and cons
-------------

There are a couple of advantages to this design in which we use a consensus
protocol to sequence transactions.

A storage provider only needs to send its proofs to a single validator, and
the consensus protocol ensures that all validators see it.

There is no need for validators to sign off on individual storage proofs. The
[Mysticeti paper][6] points out that signing and verifying signatures is one of
the main contributors to latency in a consistent broadcast design. By only
signing entire blocks of transactions this is avoided in the Mysticeti protocol.

This design is suitable for supporting other kinds of transactions later on,
such as payments, payment channels, and marketplace interactions.

Compared to a [previous iteration][7] of this design we have one less role.
There no longer is a separate role that monitors the on-chain marketplace to
check which storage proofs are required. Also, there is no longer a race to go
on-chain to mark a proof as missing. Because we have a consensus protocol we can
select which validator goes on-chain.

In exchange for these advantages we have some drawbacks as well.

The number of validators is by necessity fairly small (in the order of < 100
validators) because of the communication between the validators. Measures can be
taken to increase the decentralization of the validators. We could for example
introduce epochs in which some validators are chosen from a larger set of
potential validators, but that comes at the expense of added complexity.

The latency is larger than in a [previous iteration][7] of this design, because
the consensus protocol requires 3 rounds of communication before it has
sequenced the transactions. That might be mitigated by using the fast path from
the Mysticeti protocol for `StorageProof` transactions.

[7]: https://github.com/codex-storage/codex-research/pull/194
