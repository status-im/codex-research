Storage proofs & erasure coding
===============================

Authors: Codex Team

Erasure coding is used for multiple purposes in Codex:

- To restore data when a host drops from the network; other hosts can restore
  the data that the missing host was storing.
- To speed up downloads
- To increase the probability of detecting missing data on a host

The first two purposes can be handled quite effectively by expanding and
splitting a dataset using a standard erasure coding scheme, whereby each of the
resulting pieces is distributed to a different host. These hosts enter into a
contract with a client to store their piece. Their part of the contract [is
called a 'slot'][0], so we'll refer to the piece that a single hosts stores as
its 'slot data'.

In the rest of this document we will ignore these two first purposes and dive
deeper into the third purpose; increasing the probabily of finding missing slot
data on a host. For this reason we introduce a secondary erasure coding scheme
that makes it easier to detect missing or corrupted slot data on a host through
storage proofs.

Storage proofs
--------------

Our proofs of storage allow a host to prove that they are still in possession of
the slot data that they promised to hold. A proof is generated by sampling a
number of blocks and providing a Merkle proof for those blocks. The Merkle proof
is generated inside a SNARK to compress it to a small size to allow for
cost-effective verification on a blockchain.

Erasure coding increases the odds of detecting missing slot data with these
proofs.

Consider this example without erasure coding:

    -------------------------------------
    |///|///|///|///|///|///|///|   |///|
    -------------------------------------
                                  ^
                                  |
                                missing


When we query a block, we have a low chance of detecting the missing block. But
the slot data can no longer be considered to be complete, because a single block
is missing.

When we add erasure coding:

    ---------------------------------     ---------------------------------
    |   |///|   |///|   |   |   |///|     |///|///|   |   |///|///|   |   |
    ---------------------------------     ---------------------------------
            original data                             parity data

In this example, more than 50% of the erasure coded data needs to be missing
before the slot data can no longer be considered complete. When we now query a
block from this dataset, we have a more than 50% chance of detecting a missing
block. And when we query multiple blocks, the odds of detecting a missing block
increase exponentially.

Erasure coding
--------------

Reed-Solomon erasure coding works by representing data as a polynomial, and then
sampling parity data from that polynomial.

                    __
      __           /  \      __                     __
     /  \         /    \    /  \                   /  \
    /    \       /      \__/    \    __           /
          --    /                \__/  \       __/
            \__/                        \     /
                    ^                    \   /       |
                    |                     ---        |
     ^  ^           |  ^        |                    |
     |  |        ^  |  |  ^     |  |  |           |  |
     |  |  ^     |  |  |  |     |  |  |        |  |  |
     |  |  |  ^  |  |  |  |     |  |  |  |  |  |  |  |
     |  |  |  |  |  |  |  |     |  |  |  |  |  |  |  |
     |  |  |  |  |  |  |  |     v  v  v  v  v  v  v  v

    -------------------------  -------------------------
    |//|//|//|//|//|//|//|//|  |//|//|//|//|//|//|//|//|
    -------------------------  -------------------------

         original data                  parity


This only works for small amounts of data. When the polynomial is for instance
defined over byte sized elements from a Galois field of 2^8, you can only encode
2^8 = 256 bytes (data and parity combined).

Interleaving
------------

To encode larger pieces of data with erasure coding, interleaving is used. This
works by taking larger shards of data, and encoding smaller elements from these
shards.

    data shards

    -------------    -------------    -------------    -------------
    |x| | | | | |    |x| | | | | |    |x| | | | | |    |x| | | | | |
    -------------    -------------    -------------    -------------
     |                /                /                |
      \___________   |   _____________/                 |
                  \  |  /  ____________________________/
                   | | |  /
                   v v v v

                  ---------         ---------
            data  |x|x|x|x|   -->   |p|p|p|p|  parity
                  ---------         ---------

                                     | | | |
       _____________________________/ /  |  \_________
      /                 _____________/   |             \
     |                 /                /               |
     v                v                v                v
    -------------    -------------    -------------    -------------
    |p| | | | | |    |p| | | | | |    |p| | | | | |    |p| | | | | |
    -------------    -------------    -------------    -------------

    parity shards

This is repeated for each element inside the shards. In this manner, we can
employ erasure coding on a Galois field of 2^8 to encode 256 shards of data, no
matter how big the shards are.

The number of original data shards is typically called K, the number of parity
shards M, and the total number of shards N.

Adversarial erasure
-------------------

The disadvantage of interleaving is that it weakens the protection against
adversarial erasure that Reed-Solomon provides.

An adversarial host can now strategically remove only the first element from
more than half of the shards, and the slot data can no longer be recovered from
the data that the host stores. For example, with 1TB of slot data erasure coded
into 256 data and parity shards, an adversary could strategically remove 129
bytes, and the data can no longer be fully recovered with the erasure coded data
that is present on the host.

Implications for storage proofs
-------------------------------

This means that when we check for missing data, we should perform our checks on
entire shards to protect against adversarial erasure. In the case of our Merkle
storage proofs, this means that we need to hash the entire shard, and then check
that hash with a Merkle proof. Effectively the block size for Merkle proofs
should equal the shard size of the erasure coding interleaving. This is rather
unfortunate, because hashing large amounts of data is rather expensive to
perform in a SNARK, which is what we use to compress proofs in size.

A large amount of input data in a SNARK leads to a larger circuit, and to more
iterations of the hashing algorithm, which also leads to a larger circuit. A
larger circuit means longer computation and higher memory consumption.

Ideally, we'd like to have small blocks to keep Merkle proofs inside SNARKs
relatively performant, but we are limited by the maximum number of shards that a
particular Reed-Solomon algorithm supports. For instance, the [leopard][1]
library can create at most 65536 shards, because it uses a Galois field of 2^16.
Should we use this to encode a 1TB slot, we'd end up with shards of 16MB, far
too large to be practical in a SNARK.

Design space
------------

This limits the choices that we can make. The limiting factors seem to be:

- Maximum number of shards, determined by the field size of the erasure coding
  algorithm
- Number of shards per proof, which determines how likely we are to detect
  missing shards
- Capacity of the SNARK algorithm; how many bytes can we hash in a reasonable
  time inside the SNARK

From these limiting factors we can derive:

- Block size; equals shard size
- Maximum slot size; the maximum amount of data that can be verified with a
  proof
- Erasure coding memory requirements

For example, when we use the leopard library, with a Galois field of 2^16, and
require 80 blocks to be sampled per proof, and we can implement a SNARK that can
hash 80*64K bytes, then we have:

- Block size: 64KB
- Maximum slot size: 4GB (2^16 * 64KB)
- Erasure coding memory: > 128KB (2^16 * 16 bits)

Which has the disadvantage of having a rather low maximum slot size of 4GB. When
we want to improve on this to support e.g. 1TB slot sizes, we'll need to either
increase the capacity of the SNARK, increase the field size of the erasure
coding algorithm, or decrease the durability guarantees.

> The [accompanying spreadsheet][4] allows you to explore the design space
> yourself

Increasing SNARK capacity
-------------------------

Increasing the computational capacity of SNARKs is an active field of study, but
it is unlikely that we'll see an implementation of SNARKS that is 100-1000x
faster before we launch Codex. Better hashing algorithms are also being designed
for use in SNARKS, but it is equally unlikely that we'll see such a speedup here
either.

Decreasing durability guarantees
--------------------------------

We could reduce the durability guarantees by requiring e.g. 20 instead of 80
blocks per proof. This would still give us a probability of detecting missing
data of 1 - 0.5^20, which is 0.999999046, or "six nines". Arguably this is still
good enough. Choosing 20 blocks per proof allows for slots up to 16GB:

- Block size: 256KB
- Maximum slot size: 16GB (2^16 * 256KB)
- Erasure coding memory: > 128KB (2^16 * 16 bits)

Erasure coding field size
-------------------------

If we could perform erasure coding on a field of around 2^20 to 2^30, then this
would allow us to get to larger slots. For instance, with a field of at least
size 2^24, we could support slot sizes up to 1TB:

- Block size: 64KB
- Maximum slot size: 1TB (2^24 * 64KB)
- Erasure coding memory: > 48MB (2^24 * 24 bits)

We are however unaware of any implementations of reed solomon that use a field
size larger than 2^16 and still be efficient O(N log(N)). [FastECC][2] uses a
prime field of 20 bits, but its decoder isn't released yet, and it is unclear
whether its byte encoding scheme allows for a systematic erasure code. The paper
["An Efficient (n,k) Information Dispersal Algorithm Based on Fermat Number
Transforms"][3] describes a scheme that uses Proth fields of 2^30, but lacks an
implementation, and has the same encoding challenges that FastECC has.

If we were to adopt an erasure coding scheme with a large field, it is likely
that we'll either have to modify Leopard or FastECC, or implement one ourselves.

More dimensions
---------------

Another thing that we could do is to keep using existing erasure coding
implementations, but perform erasure coding in more than one dimension. For
instance with two dimensions you would encode first in rows, and then in
columns:

      original data                        row parity

    ---------------------------------    -------------
    |///|///|///|///|///|///|///|///| -> | p | p | p |
    ---------------------------------    -------------
    |///|///|///|///|///|///|///|///| -> | p | p | p |
    ---------------------------------    -------------
    |///|///|///|///|///|///|///|///| -> | p | p | p |
    ---------------------------------    -------------
    |///|///|///|///|///|///|///|///| -> | p | p | p |
    ---------------------------------    -------------
    |///|///|///|///|///|///|///|///| -> | p | p | p |
    ---------------------------------    -------------
    |///|///|///|///|///|///|///|///| -> | p | p | p |
    ---------------------------------    -------------
    |///|///|///|///|///|///|///|///| -> | p | p | p |
    ---------------------------------    -------------
    |///|///|///|///|///|///|///|///| -> | p | p | p |
    ---------------------------------    -------------
      |   |   |   |   |   |   |   |        |   |   |
      v   v   v   v   v   v   v   v        v   v   v
    ---------------------------------    -------------
    | p | p | p | p | p | p | p | p |    | p | p | p |
    ---------------------------------    -------------
    | p | p | p | p | p | p | p | p |    | p | p | p |
    ---------------------------------    -------------
    | p | p | p | p | p | p | p | p |    | p | p | p |
    ---------------------------------    -------------

                        column parity

This allows us to use the maximum number of shards for our rows, and the maximum
number of shards for our columns. When we erasure code using a Galois field of
2^16 in a two-dimensional structure, we can now have a maximum of 2^16 x 2^16 =
2^32 shards. Or we could go up another two dimensions and have a maximum of 2^64
shards in a four-dimensional structure.

> Note that although we now have multiple dimensions of erasure coding, we do
> not need multiple dimensions of Merkle trees. We can simply unfold the
> multi-dimensional structure into a one-dimensional one (like you would do when
> writing the structure to disk), and then construct a Merkle tree on top of
> that.

There are however a number of drawbacks to adding more dimensions.

##### Data corrupted sooner #####

In a one-dimensional scheme, corrupting a number of shards just larger than the
number of parity shards ( M + 1 ) will render the slot data incomplete:


                                 <--------- missing: M + 1---------------->
    ---------------------------------     ---------------------------------
    |///|///|///|///|///|///|///|   |     |   |   |   |   |   |   |   |   |
    ---------------------------------     ---------------------------------
    <-------- original: K ---------->     <-------- parity: M ------------>

In a two-dimensional scheme, we only need to lose an amount much smaller than
the total amount of parity before the slot data becomes incomplete:


    <-------- original: K ---------->   <- parity: M ->

    ---------------------------------    -------------   ^
    |///|///|///|///|///|///|///|///|    |///|///|///|   |
    ---------------------------------    -------------   |
    |///|///|///|///|///|///|///|///|    |///|///|///|   |
    ---------------------------------    -------------   |
    |///|///|///|///|///|///|///|///|    |///|///|///|   |
    ---------------------------------    -------------   |
    |///|///|///|///|///|///|///|///|    |///|///|///|   |
    ---------------------------------    -------------
    |///|///|///|///|///|///|///|///|    |///|///|///|   K
    ---------------------------------    -------------
    |///|///|///|///|///|///|///|///|    |///|///|///|   |
    ---------------------------------    -------------   |
    |///|///|///|///|///|///|///|///|    |///|///|///|   |
    ---------------------------------    -------------   |    ^
    |///|///|///|///|///|///|///|   |    |   |   |   |   |    |
    ---------------------------------    -------------   v    |

    ---------------------------------    -------------   ^    M
    |///|///|///|///|///|///|///|   |    |   |   |   |   |    +
    ---------------------------------    -------------        1
    |///|///|///|///|///|///|///|   |    |   |   |   |   M
    ---------------------------------    -------------        |
    |///|///|///|///|///|///|///|   |    |   |   |   |   |    |
    ---------------------------------    -------------   v    v

                                <-- missing: M + 1 -->

This is only (M + 1)² shards from a total of N² shards. This gets worse when you
go to three, four or higher dimensions. This means that our chances of detecting
whether the data is incomplete go down, which means that we need to check more
shards in our Merkle storage proofs. This is exacerbated by the need to counter
parity blowup.

##### Parity blowup ######

When we perform a regular one-dimensional erasure coding, we like to use a ratio
of 1:2 between original data (K) and total data (N), because it gives us a >50%
chance of detecting incomplete data by checking a single shard. If we were to
use the same K and M in a 2-dimensional setting, we'd get a ratio of 1:4 between
original data and total data. In other words, we would blow up the original data
by a factor of 4. This gets worse with higher dimensions.

To counter this blow-up, we can choose an M that is smaller. For two dimensions,
we could choose K = N / √2, and therefore M = N - N / √2. This ensures that the
total amount of data N² is double that of the original data K². For three
dimensions we'd choose K = N / ∛2, etc. This however means that the chances of
detecting incomplete rows or columns go down, which means that we'd again have
to sample more shards in our Merkle storage proofs.

##### Larger encoding times #####

Another drawback of multi-dimensional erasure coding is that we now need to
erasure code the original data multiple times, and we also need to erasure code
some of the parity data. For a two-dimensional code this means that encoding
times go up by a factor of at least 2, and for a three-dimensional a factor of
at least 3, etc.

##### Complexity #####

The final drawback of multi-dimensional erasure coding is its complexity. It is
harder to reason about its correctness, and implementations must take great care
to ensure that cornercases when the data is not exactly K² shaped (or K³, or...)
are handled correctly. Decoding is also more involved because it might require
restoring parity data before it is possible to restore the original data.

##### The good news ####

Despite these drawbacks, the multi-dimensional approach allows us to make the
shards almost arbitrarily small. This allows us to compensate for the need to
sample more shards in our Merkle proofs. For example, using a 2 dimensional
structure of erasure coded shards in a Galois field of 2^16, we can handle 1TB
of data with shards of size 256 bytes. When we allow parity data to take up to
half of the total data, we would need to sample 160 shards to have a 0.999999
chance of detecting incomplete slot data. This is much more than the number of
shards that we need in a one-dimensional setting, but the shards are much
smaller. This leads to less hashing in a SNARK, just 40 KB.

> The numbers for multi-dimensional erasure coding schemes can be found in the
> [accompanying spreadsheet][4]

Conclusion
----------

It is likely that with the current state of the art in SNARK design and erasure
coding implementations we can only support slot sizes up to 4GB. There are two
design directions that allow an increase of slot size. One is to extend or
implement an erasure coding implementation to use a larger field size. The other
is to use existing erasure coding implementation in a multi-dimensional setting.

Two concrete options are:

1. Erasure code with a field size that allows for 2^28 shards. Check 20 shards
   per proof. For 1TB this leads to shards of 4KB. This means the SNARK needs to
   hash 80KB plus the Merkle paths for a storage proof. Requires custom
   implementation of Reed-Solomon, and requires at least 1 GB of memory while
   performing erasure coding.
2. Erasure code with a field size of 2^16 in two dimensions. Check 160 shards
   per proof. For 1TB this leads to a shards of 256 bytes. This means that the
   SNARK needs to hash 40KB plus the Merkle paths for a storage proof. We can
   use the leopard library for erasure coding and keep memory requirements for
   erasure coding to a negligable level.

[0]: ./marketplace.md
[1]: https://github.com/catid/leopard
[2]: https://github.com/Bulat-Ziganshin/FastECC
[3]: https://ieeexplore.ieee.org/abstract/document/6545355
[4]: ./proof-erasure-coding.ods