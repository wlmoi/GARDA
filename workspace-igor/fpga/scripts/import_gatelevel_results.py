"""Record supplied JUnit/FST evidence without promoting functional PASS to physical sign-off."""
from pathlib import Path,PurePosixPath
import argparse,hashlib,json,shutil,subprocess,xml.etree.ElementTree as ET,zipfile
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'evidence/asic_import/gatelevel_test_results'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('archive',type=Path);args=p.parse_args()
    OUT.mkdir(parents=True,exist_ok=True);dest=OUT/'source.zip'
    if args.archive.resolve()!=dest.resolve():shutil.copyfile(args.archive,dest)
    with zipfile.ZipFile(dest) as z:
        assert z.testzip() is None
        for entry in z.infolist():
            path=PurePosixPath(entry.filename)
            if path.is_absolute() or '..' in path.parts or '\\' in entry.filename or ':' in entry.filename:raise ValueError(entry.filename)
            if entry.is_dir():continue
            target=OUT/'raw'/entry.filename;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(z.read(entry))
    xml=ET.parse(OUT/'raw/results.xml').getroot();tests=[]
    for case in xml.iter('testcase'):
        tests.append({**case.attrib,'status':'FAIL' if case.find('failure') is not None or case.find('error') is not None else 'SKIP' if case.find('skipped') is not None else 'PASS'})
    assert tests,'No testcase evidence'
    status='PASS' if all(t['status']=='PASS' for t in tests) else 'NOT_ALL_PASS'
    converter=Path('C:/iverilog/gtkwave/bin/fst2vcd.exe')
    subprocess.run([str(converter),'-f',str(OUT/'raw/tb.fst'),'-o',str(OUT/'raw/tb.vcd')],check=True,capture_output=True)
    scopes=[];signals=[];header=[]
    with (OUT/'raw/tb.vcd').open() as stream:
        for line in stream:
            header.append(line)
            parts=line.split()
            if parts[:1]==['$scope']:scopes.append(parts[2])
            elif parts[:1]==['$upscope']:scopes.pop()
            elif parts[:1]==['$var']:signals.append('.'.join(scopes+[parts[4]]))
            elif parts[:1]==['$enddefinitions']:break
    record={'functional_test_status':status,'testcases':tests,'random_seed':[x.attrib for x in xml.iter('property')],
            'waveform_signals':len(signals),'source_archive_sha256':sha(dest),
            'physical_signoff_status':'NOT_ESTABLISHED_BY_GATELEVEL_XML',
            'notes':['XML confirms supplied functional test result; not rerun locally.',
                     'Simulation wall time and sim_time_ns are not inference latency.',
                     'No SDF annotation log, netlist/GDS hash or precheck result is contained in this two-file archive.']}
    (OUT/'summary.json').write_text(json.dumps(record,indent=2)+'\n')
    (OUT/'waveform_signals.txt').write_text('\n'.join(signals)+'\n')
    (OUT/'README.md').write_text('# Gate-level test results supplied by user\n\n'
        f'**Functional GL test: {status}.** {len(tests)} testcase(s); no failure/error elements for passing cases.\n\n'
        'Source: [results.xml](raw/results.xml), [original FST](raw/tb.fst), [converted VCD](raw/tb.vcd), '
        '[all waveform signal names](waveform_signals.txt), [summary](summary.json).\n\n'
        'This imports the supplied result; it does not claim a new local simulation run. '
        'The archive has only results.xml and tb.fst, so physical timing closure, SDF annotation, source/netlist/GDS '
        'identity and Tiny Tapeout precheck are not established by these files. '
        'Keep GL PASS separate from the nonzero timing/DRV/overlap metrics in the GDS diagnostics.\n',encoding='utf-8')
    manifest={p.relative_to(OUT).as_posix():sha(p) for p in OUT.rglob('*') if p.is_file() and p.name!='manifest.json'}
    (OUT/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(json.dumps(record,indent=2))
if __name__=='__main__':main()
