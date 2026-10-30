"""Audit bank mapping, numerical/transport evidence, fitted resources and timing."""
from pathlib import Path
import argparse, csv, hashlib, json, re, sys
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def readlog(p):
    return p.read_text(encoding='utf-16' if p.read_bytes()[:2]==b'\xff\xfe' else 'utf-8-sig')
def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--simulation-only',action='store_true')
    args=parser.parse_args()
    words=(ROOT/'rtl/igor_src_policy/policy_weights.mem').read_text().split()
    banks=[(HERE/f'bank{i}.mem').read_text().split() for i in range(8)]
    count=0
    for rows,cols,base,bias,bw,bb in [(128,74,0,9472,0,1184),(64,128,9600,17792,1200,2224),(3,64,17856,18048,2232,2296)]:
        for neuron in range(rows):
            lane=neuron%8; group=neuron//8
            for k in range(cols):
                assert banks[lane][bw+group*cols+k]==words[base+neuron*cols+k]
                count+=1
            assert banks[lane][bb+group]==words[bias+neuron]
            count+=1
    assert count==18051
    for lane in range(3,8): assert all(x=='0000' for x in banks[lane][2232:2297])
    for bank in banks: assert len(bank)==4096 and all(x=='0000' for x in bank[2297:])
    report={'status':'PASS','bank_words_verified':count,'clock_hz':50000000,
            'cycles':6916,'latency_ms':6916/50000,'target_ms':0.16,
            'hardware_measured':False,'suites':{}}
    for suite in ['core','uart','board']:
        log=readlog(HERE/f'artifacts/{suite}.log')
        assert f'PASS {suite}' in log and 'FATAL' not in log and 'ERROR:' not in log
        match=re.search(r'(\d+) (assertions|checkpoints)',log)
        report['suites'][suite]={match[2]:int(match[1]),'passed':True}
    rows=list(csv.DictReader((HERE/'core_checkpoints.csv').open()))
    for tid in ['0','1']:
        start=next(r for r in rows if r['test_id']==tid and r['event']=='inference_started')
        done=next(r for r in rows if r['test_id']==tid and r['event']=='bit_exact_complete')
        assert int(done['cycle'])-int(start['cycle'])==6916
        assert int(done['latency_cycles'])==6916
    simulated=json.loads((HERE/'artifacts/results.json').read_text())
    for path,digest in simulated['sha256'].items(): assert sha(ROOT/path)==digest, path
    if args.simulation_only:
        report['status']='SIMULATION_PASS_FITTING_NOT_CHECKED'
        (HERE/'artifacts/simulation_acceptance.json').write_text(json.dumps(report,indent=2)+'\n')
        print(json.dumps(report,indent=2))
        return
    fit=HERE/'output_files/igor_src_policy.fit.summary'
    assert fit.is_file(),'Quartus fitting not complete'
    assert 'Quartus Prime Full Compilation was successful' in readlog(HERE/'artifacts/compile.log')
    text=fit.read_text()
    assert 'Successful' in text
    report['fitter_summary']=text
    sta=HERE/'output_files/igor_src_policy.sta.summary'
    timing=re.findall(r'Type\s*:\s*(.*?)\r?\nSlack\s*:\s*([-+\d.]+)',sta.read_text())
    assert timing and all(float(slack)>=0 for _,slack in timing),timing
    report['timing_slack_ns']={name.strip():float(slack) for name,slack in timing}
    sys.path.insert(0,str(ROOT/'scripts'))
    from build_quartus import pin_rows
    report['pins']=pin_rows(HERE/'output_files/igor_src_policy.pin')
    baseline=json.loads((ROOT/'evidence/current_builds/source_policy.json').read_text())
    assert report['pins']==baseline['pin_assignments'],'Fitted pins differ from validated board pinout'
    assert len(report['pins'])==13
    evidence=[]
    def row(metric,value,unit,path,line,kind):
        evidence.append([metric,value,unit,path.relative_to(ROOT).as_posix(),line,sha(path),kind])
    report['resources']={}
    for key,label,unit in [('alm','Logic utilization (in ALMs)','ALM'),('registers','Total registers','register'),('m10k','Total RAM Blocks','M10K'),('dsp','Total DSP Blocks','DSP'),('memory_bits','Total block memory bits','bit')]:
        line=next((i,s) for i,s in enumerate(text.splitlines(),1) if s.startswith(label+' :'))
        value=int(re.search(r':\s*([\d,]+)',line[1])[1].replace(',',''))
        report['resources'][key]=value;row(key,value,unit,fit,line[0],'post-fit resource count')
    report['power']={}
    for profile in ['typical','maximum_tj100']:
        summary=HERE/f'artifacts/power/{profile}/igor_src_policy.pow.summary'
        full=summary.with_suffix('.rpt')
        detail=full.read_text()
        assert re.search(r'Enable HPS\s*; Off\s*;',detail)
        if profile=='maximum_tj100':
            assert re.search(r'Device Power Characteristics\s*; MAXIMUM\s*;',detail)
            assert re.search(r'User entered junction temperature\s*; 100\.0 degrees Celsius',detail)
        else: assert re.search(r'Device Power Characteristics\s*; TYPICAL\s*;',detail)
        values={}
        for key,label in [('total','Total Thermal Power Dissipation'),('dynamic','Core Dynamic Thermal Power Dissipation'),('static','Core Static Thermal Power Dissipation'),('io','I/O Thermal Power Dissipation')]:
            line=next((i,s) for i,s in enumerate(summary.read_text().splitlines(),1) if s.startswith(label+' :'))
            value=float(re.search(r':\s*([\d.]+) mW',line[1])[1])
            values[key]=value;row(profile+'_'+key,value,'mW',summary,line[0],'estimated FPGA thermal; HPS excluded; Low confidence')
        assert abs(values['total']-sum(values[k] for k in ['dynamic','static','io']))<=0.021
        assert 'Power Estimation Confidence : Low:' in summary.read_text()
        values['confidence']='Low'; values['hardware_measured']=False
        report['power'][profile]=values
    warnings=re.findall(r'^Warning \((\d+)\)',readlog(HERE/'artifacts/compile.log'),re.M)
    report['compile_warnings']={code:warnings.count(code) for code in sorted(set(warnings))}
    assert report['compile_warnings']=={'10030':24,'10037':24,'10230':1},'New warning requires review'
    assert 'Critical Warning' not in readlog(HERE/'artifacts/compile.log')
    row('latency_cycles',6916,'cycle',HERE/'core_checkpoints.csv',3,'RTL simulation; core only')
    row('clock_period',20,'ns',HERE/'igor_src_policy.sdc',1,'timing constraint; validated by STA')
    with (HERE/'artifacts/metric_evidence.csv').open('w',newline='') as stream:
        writer=csv.writer(stream);writer.writerow(['metric','value','unit','source','line','source_sha256','kind']);writer.writerows(evidence)
    sof=HERE/'output_files/igor_src_policy.sof'
    assert sof.is_file()
    report['sof_sha256']=sha(sof)
    files=list(HERE.glob('*.v'))+list(HERE.glob('*.sv'))+list(HERE.glob('*.mem'))+list(HERE.glob('*.q*'))+list(HERE.glob('*.sdc'))+[HERE/'pin_assignment.tcl']
    files+=list((HERE/'artifacts').glob('*.log'))+list((HERE/'artifacts').glob('*.csv'))+list((HERE/'output_files').glob('*.rpt'))+list((HERE/'output_files').glob('*.summary'))
    files+=list((HERE/'output_files').glob('*.pin'))
    files+=list(HERE.glob('*.py'))+list(HERE.glob('*.md'))+list(HERE.glob('*.csv'))
    files += [p for p in (HERE/'artifacts').rglob('*') if p.is_file() and p.suffix in {'.gz','.png','.json','.rpt','.summary','.gtkw','.tcl','.log'} and p.name!='acceptance.json']
    files += [ROOT/'rtl/igor_src_policy/igor_src_policy_uart.v',ROOT/'rtl/igor_uart_rx.v',ROOT/'rtl/igor_uart_tx.v',ROOT/'rtl/igor_src_policy/policy_weights.mem']
    report['sha256']={p.relative_to(ROOT).as_posix():sha(p) for p in sorted(files)}
    (HERE/'artifacts/acceptance.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:report[k] for k in ['status','bank_words_verified','latency_ms','suites','timing_slack_ns']},indent=2))
if __name__=='__main__': main()
