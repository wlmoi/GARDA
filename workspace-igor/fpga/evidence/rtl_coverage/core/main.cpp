#include "Vtb_src_policy_core.h"
#include "verilated.h"
#include "verilated_cov.h"
int main(int argc,char** argv) {
 VerilatedContext context; context.commandArgs(argc,argv);
 Vtb_src_policy_core model{&context};
 while(!context.gotFinish()) { model.eval();
  if(!model.eventsPending()) break;
  context.time(model.nextTimeSlot());
 }
 model.final(); VerilatedCov::write("coverage.dat");
 return context.gotFinish()?0:2;
}
