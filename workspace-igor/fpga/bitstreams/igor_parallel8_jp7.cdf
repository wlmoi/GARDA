JedecChain;
FileRevision(JESD32A);
DefaultMfr(6E);
P ActionCode(Ign)
 Device PartName(SOCVHPS) MfrSpec(OpMask(0));
P ActionCode(Cfg)
 Device PartName(5CSEBA6) Path("./") File("igor_parallel8_jp7.sof") MfrSpec(OpMask(1));
ChainEnd;
AlteraBegin;
ChainType(JTAG);
AlteraEnd;
