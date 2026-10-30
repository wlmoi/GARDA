/* DE10-Nano chain observed and programmed successfully on 2026-10-18.
   HPS @1 bypass; FPGA @2 configured. Keep this file beside the SOF. */
JedecChain;
FileRevision(JESD32A);
DefaultMfr(6E);
P ActionCode(Ign)
  Device PartName(SOCVHPS) MfrSpec(OpMask(0));
P ActionCode(Cfg)
  Device PartName(5CSEBA6) Path("./") File("igor_src_policy_parallel8.sof") MfrSpec(OpMask(1));
ChainEnd;
AlteraBegin;
ChainType(JTAG);
AlteraEnd;
