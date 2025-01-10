An evaluation of the Filecoin whitepaper
========================================

2020-12-08 Mark Spanbroek

https://filecoin.io/filecoin.pdf

Goal of this evaluation is to find things to adopt or avoid while designing
Dagger. It is not meant to be a criticism of Filecoin.

#### Pros:

+ Clients do not need to actively monitor hosts. Once a deal has been agreed
  upon, the network checks proofs of storage.
+ The network actively tries to repair storage faults by introducing new
  orders in the storage market. (§4.3.4).
+ Integrity is achieved because files are addressed using their content
  hash (§4.4).
+ Marketplaces are explicitly designed and specified (§5).
+ Micropayments via payment channels (§5.3.1).
+ Integration with other blockchain systems such as Ethereum (§7.2) are being
  worked on.

#### Cons:

- Filecoin requires its own very specific blockchain, which influences a lot
  of its design. There is tight coupling between the blockchain, storage
  accounting, proofs and markets.
- A miners influence is proportional to the amount of storage they're
  providing (§1.2), which is an incentive to become big. This could lead to
  the same centralization issues that plague Bitcoin.
- Incentives are geared towards making the particulars of the Filecoin
  design work, instead of directly aligned with users' interest. For instance,
  there are incentives for storage and retrieval, but it seems that a miner
  would be able to make money by only storing data, and never offering it for
  retrieval. Also, the incentive for a miner to store multiple independent
  copies does not mean protection against loss if they're all located on the
  same failing disk.
- The blockchain contains a complete allocation table of all things that are
  stored in the network (§4.2), which raises questions about scalability.
- Zero cash entry (such as in Swarm) doesn't seem possible.
- Consecutive micropayments are presented as a solution for the trust problems
  while retrieving (§5.3.1), which doesn't entirely mitigate withholding
  attacks.
- The addition of smart contracts (§7.1) feels like an unnecessary
  complication.
- The data are stored in a non-readable (sealed) format (§3.4.2).
  If the hosts doesn't store data in a duplicated, plain format,
  the unsealing required to read them take a long time (1-5 hours).
