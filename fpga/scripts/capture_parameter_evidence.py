"""Capture local report-reader HTML with Edge headless; never mimic Quartus UI."""
from pathlib import Path
import hashlib, html, json, subprocess, zipfile

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'fpga/evidence/parameter_screenshots'
P=Path('fpga/experiments/parallel8')
EDGE=Path('C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe')

def digest(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):
    raw=(ROOT/p).read_bytes()
    try: text=raw.decode('utf-16' if raw.startswith(b'\xff\xfe') else 'utf-8-sig')
    except UnicodeDecodeError: text=raw.decode('cp1252')
    return text.splitlines()
def excerpt(p, predicate=None, start=None, end=None):
    lines=read(p)
    chosen=[(n,line) for n,line in enumerate(lines,1) if (predicate(line) if predicate else (start or 1)<=n<=(end or len(lines)))]
    body='\n'.join(f'{n:4} | {line}' for n,line in chosen)
    return f'<div class="source">SOURCE: {html.escape(str(p))}<br>SHA256: {digest(ROOT/p)}</div><pre>{html.escape(body)}</pre>',{'path':str(p).replace('\\','/'),'sha256':digest(ROOT/p),'lines':[n for n,_ in chosen]}
def table(headers,rows):
    return '<table><tr>'+''.join('<th>'+html.escape(str(c))+'</th>' for c in headers)+'</tr>'+''.join('<tr>'+''.join('<td>'+html.escape(str(c))+'</td>' for c in row)+'</tr>' for row in rows)+'</table>'

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    inventory=[]
    def page(name,title,description,sections,extra=''):
        refs=[s[1] for s in sections]
        doc='''<!doctype html><meta charset="utf-8"><style>
        *{box-sizing:border-box}body{margin:0;background:#edf2f8;color:#13223a;font:20px Segoe UI,Arial;padding:38px}
        header{border-top:9px solid #146b83;background:white;padding:24px 30px;border-radius:12px}h1{font-size:33px;margin:8px 0 14px}
        .badge{color:#166076;font-weight:700;letter-spacing:1px;font-size:15px}p{line-height:1.45;margin:12px 0}
        .source{font:15px Consolas,monospace;background:#dfedf4;padding:14px;overflow-wrap:anywhere;margin-top:20px}
        pre{font:18px/1.5 Consolas,monospace;background:white;border:1px solid #c2d0dd;margin:0;padding:16px;white-space:pre-wrap;overflow-wrap:anywhere}
        table{width:100%;border-collapse:collapse;background:white;margin-top:20px;font-size:21px}td,th{padding:14px;border:1px solid #bfd0de;text-align:left}th{background:#163f57;color:white}
        footer{font-size:15px;margin-top:20px;color:#43566b}.note{background:#fff2ce;padding:15px;border-left:5px solid #c08a12}
        </style>'''+f'<header><div class="badge">IGOR PARALLEL8 · TRACEABLE PARAMETER EVIDENCE</div><h1>{html.escape(title)}</h1><p>{html.escape(description)}</p><p class="note">Actual browser screenshot of a local report reader. NOT a Quartus GUI screenshot. Source excerpts retain original text and line numbers; extracted tables and calculations are labelled.</p></header>'+extra+''.join(s[0] for s in sections)+'<footer>Capture: 19 October 2026 · FPGA reports: accepted Parallel8 build, 17 October 2026 · Imported ASIC scope: tt_um_igorchip protocol engine, not a mapped PPO neural ASIC.</footer>'
        target=OUT/(name+'.html'); target.write_text(doc,encoding='utf-8')
        png=OUT/(name+'.png')
        cmd=[str(EDGE),'--headless','--disable-gpu','--no-first-run','--hide-scrollbars',
             '--user-data-dir='+str(ROOT/'fpga/.runtime/parameter_capture_edge'),
             '--window-size=1900,1900','--screenshot='+str(png),target.as_uri()]
        proc=subprocess.run(cmd,capture_output=True,timeout=45,creationflags=0x08000000)
        if not png.is_file(): raise RuntimeError(proc.stderr.decode(errors='replace')[-1500:])
        assert png.read_bytes().startswith(b'\x89PNG\r\n\x1a\n')
        inventory.append({'png':png.name,'html':target.name,'png_sha256':digest(png),'html_sha256':digest(target),'sources':refs})
        print('Captured '+png.name,flush=True)
    page('01_fitted_resources','01 | Complete FPGA: logic, registers, memory, DSP, pins, PLL',
         'Raw Fitter summary. Top: igor_src_policy_de10_nano; device 5CSEBA6U23I7. These totals include the UART policy wrapper.',
         [excerpt(P/'output_files/igor_src_policy.fit.summary')])
    area=json.loads((ROOT/'fpga/evidence/area_analysis/parallel8_area.json').read_text())
    rows=[]
    for key in ('core_only','core_plus_uart_policy','board','uart_rx','uart_tx'):
        r=area['fpga'][key]; rows.append([key,r['alms_needed'],r['combinational_aluts'],r['registers'],r['m10k'],r['dsp'],r['report_line']])
    # The original table is very wide. Show selected columns as extracted values,
    # retaining exact row locations and original parenthesis-semantics note.
    fit=P/'output_files/igor_src_policy.fit.rpt'
    fields=table(['Extracted hierarchy','ALMs needed','ALUTs','Registers','M10K','DSP','Report line'],rows)
    lines=read(fit)
    compact='\n'.join(f'L{r["report_line"]}: '+ ' ; '.join(lines[r['report_line']-1].split(';')[1:3]).strip() for r in area['fpga'].values())
    excerpt_html, ref=excerpt(fit,start=1441,end=1442)
    page('02_core_uart_hierarchy','02 | Pure neural core versus UART interface',
         'Extracted columns from the actual fitted hierarchy; no re-synthesis. Inclusive hierarchy numbers are used. UART overhead = 3300.7 - 2402.7 = 898.0 ALMs.',
         [(f'<div class="source">Original hierarchy label + ALM field, source lines retained:</div><pre>{html.escape(compact)}</pre>'+excerpt_html,ref)],fields)
    inventory[-1]['sources'][0]['lines'] += [r['report_line'] for r in area['fpga'].values()]
    page('03_memory_packing','03 | SRAM-based block memory and ALM packing',
         'Configured data = 524,288 bits (64 KiB). Physical block implementation = 655,360 bits (64 x 10,240). Do not add these as two memories.',
         [excerpt(fit,start=487,end=495),excerpt(fit,start=554,end=562)])
    sta=P/'output_files/igor_src_policy.sta.rpt'
    sumsta=P/'output_files/igor_src_policy.sta.summary'
    selected_timing=set()
    sumlines=read(sumsta)
    for i,line in enumerate(sumlines):
        if line.startswith('Type  :') and ('Setup' in line or 'Hold' in line):
            selected_timing.update((line,sumlines[i+1]))
    page('04_timing_clock_fmax','04 | Clock, setup/hold slack and analysed Fmax',
         'Operating clock: 50 MHz (20 ns). Worst reported setup +5.647 ns; worst hold +0.119 ns. Analysed Fmax is not the actual running clock.',
         [excerpt(sumsta,predicate=lambda l:l in selected_timing),excerpt(sta,start=125,end=136),excerpt(sta,start=205,end=209)])
    page('05_power','05 | FPGA power estimate: dynamic, static and I/O',
         'Vectorless Power Analyzer estimate, confidence Low; not a board-current measurement. Includes full FPGA top, not isolated neural-core power.',
         [excerpt(P/'artifacts/power/typical/igor_src_policy.pow.summary'),excerpt(P/'artifacts/power/maximum_tj100/igor_src_policy.pow.summary')])
    page('06_latency_acceptance','06 | Core latency and simulation acceptance',
         '6,916 cycles / 50,000,000 Hz = 138.32 us = 0.13832 ms. This is core latency; not physical UART RTT. Throughput upper bound: 7,229.61 core inferences/s before interface overhead.',
         [excerpt(P/'artifacts/acceptance.json',start=1,end=24)])
    ap=Path('fpga/evidence/asic_import/gds_diagnostics_1/raw/runs/wokwi/final/metrics.json')
    page('07_asic_area_raw','07 | Tiny Tapeout: allocated area, standard cells and SRAM',
         'Original physical metrics, in um^2. 1 mm^2 = 1,000,000 um^2. Standard cells + macro = 97,957.9 um^2; allocated die rectangle = 916,214 um^2.',
         [excerpt(ap,predicate=lambda l:any('"'+key+'"' in l for key in ['design__die__area','design__core__area','design__instance__area','design__instance__area__stdcell','design__instance__area__macros','design__instance__count__stdcell','design__instance__count__macros','design__instance__area__class:fill_cell'])),excerpt(Path('info.yaml'),start=2,end=17)])
    calc=Path('fpga/evidence/area_analysis/parallel8_area.json')
    calctable=table(['Derived quantity','Formula','Result'],[
        ['Core ALM capacity','2402.7 / 41910 x 100','5.7330%'],
        ['Core + UART ALM capacity','3300.7 / 41910 x 100','7.8757%'],
        ['M10K capacity','64 / 553 x 100','11.5732%'],
        ['DSP capacity','8 / 112 x 100','7.1429%'],
        ['ASIC logic fraction of logic + SRAM','69830.8 / 97957.9 x 100','71.2865%'],
        ['ASIC SRAM fraction of logic + SRAM','28127.1 / 97957.9 x 100','28.7135%'],
        ['ASIC footprint / allocated die','97957.9 / 916214 x 100','10.6916%'],
        ['Same-macro 64 KiB projection','128 x 0.0281271 mm^2','3.6002688 mm^2 (memory only)']])
    page('08_calculations','08 | Percentages and memory projection: calculated evidence',
         'DERIVED VALUES, not independent tool measurements. FPGA capacity percentages have different denominators. ASIC raw metrics belong to a different design; equal-footprint allocation is hypothetical.',
         [excerpt(calc,predicate=lambda l:any(k in l for k in ['standard_cells_mm2','sram_macro_mm2','combined_die_percent','allocated_macro_count','allocated_macro_mm2','active_macro_mm2']))],calctable)
    pins=P/'output_files/igor_src_policy.pin'
    page('09_pinplan','09 | Fitted physical pins and clock constraints',
         'Pins from the fitted .pin file, not a conceptual diagram. KEY0 reset, KEY1 latched E-stop; fabric UART uses 3.3-V LVTTL.',
         [excerpt(pins,predicate=lambda l:any(s in l for s in ('FPGA_CLK1_50','KEY[','LED[','UART_RX','UART_TX'))),excerpt(P/'igor_src_policy.sdc')])
    results=Path('fpga/evidence/current_programming/20261019T0245566102607Z/programming_from_cdf.log')
    page('10_programming','10 | Actual board programming result',
         '19 October 2026: accepted Parallel8 SOF loaded via DE-SoC USB-1, HPS bypass, FPGA device @2. Configuration success is separate from runtime UART functional testing.',
         [excerpt(results,predicate=lambda l:any(s in l for s in ['Info (','0 errors','Processing started:','Processing ended:']))])
    (OUT/'screenshots_manifest.json').write_text(json.dumps({'capture_method':'Microsoft Edge headless --screenshot of local report-reader HTML; not native Quartus UI','screenshots':inventory},indent=2)+'\n')
    md='# Parameter evidence screenshots\n\nThese PNGs are genuine Edge headless captures of local report-reader pages. They are **not screenshots of the native Quartus GUI**. The Windows Computer Use runtime failed with `failed to write kernel assets: The system cannot find the path specified`, including after reset. No values were edited in the original tool reports.\n\nEach HTML retains original source paths, hashes and line numbers. Reformatted extracted columns and calculated values are labelled. No Quartus build or simulation was rerun for these captures.\n\n'
    for item in inventory:
        md+=f'- [{item["png"]}]({item["png"]}) — editable/readable source view: [{item["html"]}]({item["html"]}).\n'
    md+='\nThe supplied older PDF screenshot uses a different top/profile and resource totals. It does not establish current Parallel8 values. Core-only resources are hierarchical attribution from the same full fitted build. ASIC metrics establish the protocol-engine layout area; they do not verify a neural ASIC area. See ../../docs/AREA_CORE_UART_ASIC.md for derivations.\n\nAll PNG/HTML/source hashes and source-line coverage: screenshots_manifest.json. The ZIP includes PNGs, HTML, this index and manifest; raw reports remain at their referenced repository paths.\n'
    (OUT/'README.md').write_text(md,encoding='utf-8')
    with zipfile.ZipFile(OUT/'PARAMETER_EVIDENCE_SCREENSHOTS.zip','w',zipfile.ZIP_DEFLATED) as z:
        for f in sorted(OUT.iterdir()):
            if f.suffix in {'.png','.html','.json','.md'}: z.write(f,f.name)
    print('PASS: 10 browser captures and source manifests generated')

if __name__=='__main__': main()
