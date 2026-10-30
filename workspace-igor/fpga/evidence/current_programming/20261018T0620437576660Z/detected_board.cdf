JedecChain;
FileRevision(JESD32A);
DefaultMfr(6E);
P ActionCode(Ign)
  Device PartName(SOCVHPS) MfrSpec(OpMask(0));
P ActionCode(Cfg)
  Device PartName(5CSEBA6) Path("D:/LinkedinProjects/igor_ws/igor_ws/fpga/bitstreams/") File("igor_src_policy_parallel8.sof") MfrSpec(OpMask(1));
ChainEnd;
AlteraBegin;
ChainType(JTAG);
AlteraEnd;
