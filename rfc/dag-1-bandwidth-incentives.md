DAG1: Bandwidth Incentives
==========================

The Dagger storage network uses bandwidth incentives to ensure retrievability of
content and scaling of the network to meet demand. The rationale for incentives
is described further in a [separate document][1].

We follow the same basic design as [Sia][2], [Filecoin][3] and [Storj][4] do;
micropayments flow towards the peer which offers the content. This peer
transfers the content in small segments, waiting for payment before sending the
next segment. This reduces the risk of being cheated for both parties. These
micropayments are exchanged using a payment channel.


                           --- segments -->
                    Alice                     Bob
                           <-- payments ---


[1]: ../incentives-rationale.md
[2]: ../evaluations/sia.md
[3]: ../evaluations/filecoin.md
[4]: ../evaluations/storj.md

Payment channels
----------------

Although there are other solutions for micropayments such as sidechains and
rollups, payment channels offer the [least amount of overhead][5] for tiny
payments between peers that happen to be already connected to each other because
they are exchanging content.

There are [a number of things][6] to consider when choosing a payment channel
implementation. For our purposes the three most important criteria are (1) costs
of channel setup, (2) costs of payment routing, and (3) costs of monitoring the
underlying blockchain.

### Channel setup

Payment channels are inherently one-to-one, meaning that for every peer that a
Dagger node interacts with, a new payment channel will need to be setup. It is
therefore very important to keep the costs for setting up a new channel low.

Simple payment channels that are setup on-chain are for this reason not
practical. Which leaves us with a choice of either a payment channel network or
virtual channels.

### Payment routing

Routing payments through intermediaries introduces costs; not only because
routing through a number of nodes takes time but also because in a sustainable
network intermediaries will need to be payed for their efforts. In a payment
channel network these costs apply to every single micro-payment, because each
payment flows through a route of payment channels. With virtual channels these
costs only apply to the setup and conclusion of the channel.

### Monitoring

Payment channels require monitoring of the underlying blockchain because
disputes might occur that are adjudicated on-chain. Only simple uni-directional
payment channels do not require this, but they are impractical because of their
setup costs.

Keeping up with a blockchain requires significant bandwidth, disk space and cpu
time, which could easily outweigh the costs of participating in a storage
network. This is quite undoable for nodes on mobile devices.

Therefore monitoring will need to be outsourced to other nodes. The [PISA
protocol][7] is an example of a protocol for such outsourcing.

### Choosing a protocol

For Dagger we choose to use the [Nitro protocol][8] as implemented by
[statechannels.org][13]. This is an implementation that uses virtual channels to
minimize setup and routing costs.

We evaluated the following other payment channel implementations, and give our
subjective reasons for not choosing them:
- [Swarm's SWAP protocol][9]: allows double spending (bouncing cheques)
- [Raiden][10]: requires routing for every micropayment
- [Perun][11]: project appears to be more in the research phase than the
  engineering phase
- [Connext Vector][12]: requires routing for every micropayment

Note that we do not specify a channel monitoring protocol in this RFC. We
relegate this to a future Dagger RFC.

[5]: https://blog.statechannels.org/do-we-still-need-state-channels/
[6]: ../evaluations/statechannels.md
[7]: https://www.cs.cornell.edu/~iddo/pisa.pdf
[8]: https://magmo.com/nitro-protocol.pdf
[9]: ../evaluations/swarm.md
[10]: https://raiden.network/101.html
[11]: https://perun.network/
[12]: https://github.com/connext/vector
[13]: https://statechannels.org/

Design
------

    Peer to peer network                          Smart contracts

      --------                                    ---------------
      | Peer | <------------                      | AssetHolder |
      --------             |                      ---------------
          ^                v
          |         ----------------              --------------------
          |         | Intermediary |              | NitroAdjudicator |
          |         ----------------              --------------------
          v                ^
      --------             |                      -----------------------
      | Peer | <------------                      | SingleAssetPayments |
      --------                                    -----------------------

When two peers want to exchange micropayments, they use an intermediary to setup
a virtual payment channel. The security of the channels is ensured by smart
contracts on an Ethereum blockchain.

These are smart contracts from [statechannels.org][13]:
  - [AssetHolder][14] allows funds to be locked for use in state channels
  - [NitroAdjudicator][15] can resolve any disputes over channel outcomes
  - [SingleAssetPayments][16] models ERC-20 payments in a state channel

For now, we'll assume that there's only a single intermediary in the entire
network. We relegate the design of a routing mechanism between multiple
intermediaries to a future RFC.

[14]: https://docs.statechannels.org/docs/implementation-notes/asset-holder
[15]: https://docs.statechannels.org/docs/implementation-notes/nitro-adjudicator
[16]: https://docs.statechannels.org/docs/implementation-notes/single-asset-payments

### Deposit to ledger channel

When joining the payment network, a peer opens a ledger channel with an
intermediary. This ledger channel will later be used to fund virtual channels
with other peers.

    On-chain                        Off-chain

    ---------------                -----------------------
    | AssetHolder | --- funds ---> |   Ledger channel    |
    ---------------                -----------------------
                                    |        |          |
                                    | funds  | funds    | ...
                                    |        |          |
                                    v        v          v
                              -----------  -----------
                              | Virtual |  | Virtual |  ...
                              | Channel |  | Channel |
                              -----------  -----------

Opening a ledger channel happens in two steps:

  1. The peer and the intermediary agree on an initial state for the ledger
     channel
  2. The peer funds the ledger channel

#### Step 1: Agree on initial state

Let `x` be the amount that the peer want to make available for use in the
state channels. The initial state of the ledger channel is then as follows:

    Initial ledger channel state:
    - allocation to peer: x
    - allocation to intermediary: 0
    - app definition address: 0

The peer and the intermediary both sign this state and exchange signatures.

Note that the initial state does not reference an app definition. This signals
that there is no smart contract governing this channel. Changes to the state
of the channel can only happen when both peer and intermediary sign off on them.

#### Step 2: Fund channel

Funding should only happen after step 1 is complete. Failure to do so can lead
to loss of funds.

The peer now deposits `x` into the AssetHolder contract, referencing the id of
the ledger channel. The ledger channel is now funded.

### Open virtual channel

When two peers wish to open a virtual channel, they perform the following steps:

  1. They agree on an initial state for the virtual channel
  2. With an intermediary they setup allocation and guarantee channels
  2. They fund the channels from their respective ledger channels

#### Step 1: Agree on initial state

Both peers need to agree on an initial allocation of funds in the virtual
channel. For instance, when peer Alice wants to download content from peer Bob,
then Alice needs to allocate at least the amount of funds to cover the total
bandwidth costs of this download.

Let `a` be the amount that Alice wants to make available, and `b` be the amount
of funds that Bob wants to make available. The initial state is then as follows:

    Initial virtual channel state:
    - allocation to Alice: a
    - allocation to Bob: b
    - app definition: SingleAssetPayments

#### Step 2: Setup allocation and guarantee channels

Funding of a virtual channel from two different ledger channels requires the
following construction:


    --------------------                             --------------------
    | Ledger channel A |                             | Ledger channel B |
    --------------------                             --------------------
          |                                                       |
          v                                                       v
    -----------------------                       -----------------------
    | Guarantor channel A |--------       --------| Guarantor channel B |
    -----------------------       |       |       -----------------------
                                  |       |
                                  v       v
                           ----------------------
                           | Allocation channel |
                           ----------------------
                                      |
                                      v
                            -------------------
                            | Virtual channel |
                            -------------------

Alice, Bob, and the intermediary setup the allocation channel:

    Allocation channel initial state:
    - allocation to Alice: a
    - allocation to Bob: b
    - allocation to intermediary: a + b

Alice and the intermediary setup guarantor channel A:

    Guarantor channel A initial state:
    - guarantee target: Allocation channel
    - priority: virtual channel, Alice, intermediary

Bob and the intermediary setup guarantor channel B:

    Guarantor channel B initial state:
    - guarantee target: allocation channel
    - priority: virtual channel, Bob, intermediary

#### Step 3: Funding

Alice and Bob fund their respective guarantor channels by updating the state
of their ledger channels together with the intermediary:

    Ledger Channel A state update:
    - allocation to guarantor channel A: a + b

    Ledger Channel B state update:
    - allocation to guarantor channel B: a + b

Alice, Bob, and the intermediary fund the virtual channel using the allocation
channel:

    Allocation channel state:
    - allocation to Alice: 0
    - allocation to Bob: 0
    - allocation to intermediary: a + b
    - allocation to virtual channel: a + b

### Exchange micropayments

Once a virtual channel has been setup between peers, they can exchange
micropayments by signing and exchanging allocation updates. For instance, if
Alice want to pay `x` to Bob, then they update the state as follows:

    Virtual channel state update:
    - allocation to Alice: a - x
    - allocation to Bob: b + x

Notice that this requires only an exchange of signed updates between Alice and
Bob. Signatures from and communication with the intermediary are not necessary.

### Cashless entry

Dagger allows for cashless entry; participation in the network without a need to
lock up funds upfront. This works as follows:

  1. A new peer -Carol- opens up a ledger channel with an intermediary, with an
     allocation of 0 funds to Carol. Because Carol initially has no funds in the
     channel, the intermediary does not require a deposit from Carol in the
     `AssetHolder` contract.
  2. Carol can now start to offer services in the Dagger network, for instance
     to Dave. Carol, Dave and the intermediary can open a virtual channel, which
     allows Dave to pay Carol for services rendered. When the virtual channel is
     closed, the earned funds are moved to Carols ledger channel.

Open Questions
--------------

  1. When exchanging micropayments for downloaded segments, a profit maximizing
     peer could decide not to send the last micropayment after receiving the
     last segment. Can this be avoided?
  2. To avoid centralization in the payments network, the central intermediary
     should be replaced by a network of intermediaries, and a routing algorithm
     between them. How to design this is an open question, to be answered in a
     future RFC.
  3. Intermediaries need to lockup funds to enable the creation of virtual
     channels. They should be compensated for this with fees. How to incorporate
     fees into the virtual channel setup is an open question.
  4. The blockchain should be monitored for any challenges regarding state
     channels. How to incorporate a monitoring protocol into Dagger is an open
     question, to be answered in a future RFC.
  5. The impact on privacy of using micropayments for bandwidth needs to be
     addressed. Who can learn what you're storing and downloading on the network
     through payment channels?
  6. Pricing of bandwidth is as of yet unspecified . Does every byte downloaded
     from the network have the same price regardless of the peer it's being
     downloaded from? Do we have free downloads?
