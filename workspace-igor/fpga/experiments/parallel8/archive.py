"""Keep lossless waveforms in the candidate evidence package."""
from pathlib import Path
import gzip,hashlib,json
HERE=Path(__file__).resolve().parent
record={}
for name,source in [('core',HERE/'core.vcd'),('uart',HERE/'uart.vcd'),('board',HERE/'artifacts/board.vcd')]:
    raw=source.read_bytes()
    target=HERE/f'artifacts/{name}.vcd.gz'
    target.write_bytes(gzip.compress(raw,mtime=0))
    assert gzip.decompress(target.read_bytes())==raw
    record[name]={'raw_sha256':hashlib.sha256(raw).hexdigest(),
                  'compressed_sha256':hashlib.sha256(target.read_bytes()).hexdigest(),
                  'raw_bytes':len(raw),'compressed_bytes':target.stat().st_size}
(HERE/'artifacts/waveforms.json').write_text(json.dumps(record,indent=2)+'\n')
print('PASS lossless VCD archive:',', '.join(record))
