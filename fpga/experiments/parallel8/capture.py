"""Native GTKWave capture of the measured parallel-core completion interval."""
from pathlib import Path
import importlib.util, json, csv
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
spec=importlib.util.spec_from_file_location('capture_evidence',ROOT/'scripts/capture_visual_evidence.py')
module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
module.OUT=HERE/'artifacts'
item={'name':'core_latency','waveform':'experiments/parallel8/core.vcd',
      'checkpoint_file':'experiments/parallel8/core_checkpoints.csv',
      'time_ps':148294000,'radius_ps':150000000,'end_ps':149000000,
      'markers':[(9970000,'START'),(148290000,'DONE')],
      'signals':['tb_src_policy_core.'+s for s in ['start','busy','done','fault','error_code','latency_cycles','dut.state','dut.layer','dut.neuron','dut.k']]}
item['checkpoint']=next(r for r in csv.DictReader((HERE/'core_checkpoints.csv').open())
                        if r['test_id']=='0' and r['event']=='bit_exact_complete')
module.validate_wave_samples([item])
result=module.capture(item,Path('C:/iverilog/gtkwave/bin/gtkwave.exe'))
(HERE/'artifacts/capture.json').write_text(json.dumps(result,indent=2)+'\n')
print(result['image'])
