"""Check SRAM view/placement contracts and scoped LVS compatibility offline."""
from pathlib import Path
import ast
import json
import re
import sys
import tempfile
import unittest
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from asic.neural_sram.netgen_json import normalize_sram_power_pins, repair_report
from asic.neural_sram.abstract_overlap import qualify_overlaps

TARGET = ROOT / 'asic/neural_sram'
from asic.neural_sram.contracts import EXPECTED_INSTANCES, EXPECTED_COUNTS, PARAM_MACRO, ACT_MACRO


class IntegrationTests(unittest.TestCase):
    def test_mask_drive_repair_preserves_postgrt_flow(self):
        try:
            import tkinter
            interpreter=tkinter.Tcl()
        except Exception as error:
            self.skipTest(f'Tcl interpreter unavailable: {error}')
        with tempfile.TemporaryDirectory() as directory:
            folder=Path(directory);scripts=folder/'openroad';scripts.mkdir()
            (scripts/'repair_design_postgrt.tcl').write_text('''
lappend ::events read_design
set ::result [repair_design -verbose -slew_margin 50 -cap_margin 25]
lappend ::events legalize reroute write_views
''')
            mask=folder/'mask.tcl'
            mask.write_text('proc jp_repair_mask_drivers {} {lappend ::events mask_resize; return 2}')
            interpreter.setvar('env(SCRIPTS_DIR)',str(folder))
            # Match LibreLane's isolated subprocess environment: custom config
            # arrives only after sourcing _TCL_ENV_IN, not as an OS variable.
            interpreter.eval('unset -nocomplain ::env(NEURAL_SRAM_MASK_REPAIR)')
            env_file=folder/'_env.tcl'
            env_file.write_text('set ::env(NEURAL_SRAM_MASK_REPAIR) {'+mask.as_posix()+'}\n')
            interpreter.setvar('env(_TCL_ENV_IN)',str(env_file))
            interpreter.eval('set ::events {}; proc repair_design {args} {set ::args $args; lappend ::events original_repair; return original_result}')
            interpreter.call('source',str(TARGET/'repair_postgrt.tcl'))
            self.assertEqual(interpreter.splitlist(interpreter.getvar('events')),
                             ('read_design','original_repair','mask_resize','legalize','reroute','write_views'))
            self.assertEqual(interpreter.splitlist(interpreter.getvar('args')),
                             ('-verbose','-slew_margin','50','-cap_margin','25'))
            self.assertEqual(interpreter.getvar('result'),'original_result')
        for path in [ROOT/'src/config.json',TARGET/'config.fragment.json']:
            config=json.loads(path.read_text())
            self.assertEqual(config['meta']['substituting_steps']['OpenROAD.RepairDesignPostGRT'],
                             'Project.NeuralSRAMRepair')

    def test_overlap_step_completes_with_librelane_logging_contract(self):
        # Execute the production run method with the Step API's actual logging
        # contract: warn/err are methods, but info is a module-level function.
        tree=ast.parse((ROOT/'librelane_plugin_neural_sram.py').read_text())
        cls=next(node for node in tree.body if isinstance(node,ast.ClassDef)
                 and node.name=='NeuralSRAMAbstractOverlap')
        method=next(node for node in cls.body if isinstance(node,ast.FunctionDef)
                    and node.name=='run')
        messages=[]
        namespace={'Path':Path,'qualify_overlaps':qualify_overlaps,
                   'DesignFormat':SimpleNamespace(SPICE='spice'),'info':messages.append}
        exec(compile(ast.Module(body=[method],type_ignores=[]),str(ROOT/'librelane_plugin_neural_sram.py'),'exec'),namespace)
        config=json.loads((TARGET/'config.fragment.json').read_text())
        macros={master:SimpleNamespace(lef=[TARGET/'ihp'/(master+'.lef')],
                instances={name:SimpleNamespace(**inst) for name,inst in macro['instances'].items()})
                for master,macro in config['MACROS'].items()}
        with tempfile.TemporaryDirectory() as directory:
            folder=Path(directory)
            (folder/'feedback.txt').write_text('box 180923 21817 181177 22401\nfeedback add "Illegal overlap between obsm4 and metal4 (types do not connect)" medium\n')
            (folder/'cif_scale.txt').write_text('0.005\n')
            class InputState(dict):
                metrics={'magic__illegal_overlap__count':1,'klayout__drc_error__count':0,
                         'route__drc_errors':0,'design__power_grid_violation__count':0}
            state=InputState(spice=folder/'chip.spice')
            step=SimpleNamespace(config={'MACROS':macros},step_dir=folder)
            views,metrics=namespace['run'](step,state)
            self.assertEqual(views,{})
            self.assertEqual(metrics,{'project__unqualified_overlap__count':0,
                                     'project__sram_abstract_overlap__count':1})
            self.assertEqual(state.metrics['magic__illegal_overlap__count'],1)
            self.assertEqual(json.loads((folder/'sram_abstract_overlap.json').read_text())['status'],'PASS')
            self.assertEqual(len(messages),1)
            for key in ['klayout__drc_error__count','route__drc_errors','design__power_grid_violation__count']:
                state.metrics[key]=1
                with self.assertRaisesRegex(ValueError,key):namespace['run'](step,state)
                state.metrics[key]=0

    def test_overlap_qualification_is_limited_to_sram_power_stripes(self):
        config=json.loads((TARGET/'config.fragment.json').read_text())
        macros={master:{**macro,'lef':[str(TARGET/'ihp'/(master+'.lef'))]}
                for master,macro in config['MACROS'].items()}
        feedback='box 180923 21817 181177 22401\nfeedback add "Illegal overlap between obsm4 and metal4 (types do not connect)" medium\n'
        report=qualify_overlaps(feedback,'0.005',macros,1)
        self.assertEqual(report['qualified_sram_abstraction_count'],1)
        self.assertEqual(report['raw_magic_overlap_count'],1)
        self.assertEqual(report['unqualified_count'],0)
        for altered in [feedback.replace('obsm4','obsm3'),
                        feedback.replace('180923 21817 181177 22401','0 0 100 100'),
                        feedback.replace('180923 21817 181177 22401','180100 20000 180200 20100')]:
            with self.assertRaises(ValueError):qualify_overlaps(altered,'0.005',macros,1)
        with self.assertRaises(ValueError):qualify_overlaps(feedback,'0.005',macros,2)

    def test_tcl_resolves_openroad_escaped_bank_names(self):
        try:
            import tkinter
        except ImportError as error:
            self.skipTest(f'Tcl interpreter unavailable: {error}')
        try:
            interpreter = tkinter.Tcl()
        except tkinter.TclError as error:
            self.skipTest(f'Tcl interpreter unavailable: {error}')
        canonical = 'neural.activation_store.banks[0].i_sram'
        escaped = canonical.replace('[', '\\[').replace(']', '\\]')
        interpreter.eval('namespace eval ord {}')
        interpreter.createcommand('ord::get_db_block', lambda: 'block')
        interpreter.createcommand('block', lambda method, name:
                                  'instance0' if method == 'findInst' and name == escaped else 'NULL')
        interpreter.call('source', str(TARGET / 'sram_geometry.tcl'))
        self.assertEqual(interpreter.call('jp_find_sram', canonical), 'instance0')
        specs=interpreter.splitlist(interpreter.eval('jp_sram_specs'))
        self.assertEqual(dict(zip(specs[::2],specs[1::2])),EXPECTED_INSTANCES)

    def test_routing_report_preserves_failure_and_flags(self):
        try:
            import tkinter
            interpreter=tkinter.Tcl()
        except Exception as error:
            self.skipTest(f'Tcl interpreter unavailable: {error}')
        with tempfile.TemporaryDirectory() as directory:
            scripts=Path(directory)/'scripts';(scripts/'openroad').mkdir(parents=True)
            (scripts/'openroad/grt.tcl').write_text('global_route -congestion_iterations 50 -verbose')
            interpreter.setvar('env(SCRIPTS_DIR)',str(scripts))
            interpreter.setvar('env(SAVE_ODB)',str(Path(directory)/'result.odb'))
            interpreter.eval('proc global_route {args} {set ::captured $args; error "intentional routing failure"}')
            with self.assertRaisesRegex(tkinter.TclError,'intentional routing failure'):
                interpreter.call('source',str(TARGET/'routing_report.tcl'))
            args=interpreter.splitlist(interpreter.getvar('captured'))
            self.assertEqual(args[:3],('-congestion_iterations','50','-verbose'))
            self.assertIn('-congestion_report_file',args)
            self.assertNotIn('-allow_congestion',args)
            with self.assertRaisesRegex(tkinter.TclError,'intentional routing failure'):
                interpreter.eval('global_route -congestion_report_file custom.rpt')
            self.assertEqual(interpreter.splitlist(interpreter.getvar('captured')),
                             ('-congestion_report_file','custom.rpt'))

    def test_official_lef_and_placement_contract(self):
        config=json.loads((TARGET/'config.fragment.json').read_text())
        dimensions={PARAM_MACRO:(784.48,626.7,355,'sram_2048x64_lvs.spice'),
                    ACT_MACRO:(236.8,118.78,109,'sram_256x16_lvs.spice')}
        actual={};boxes=[]
        hx=config['FP_MACRO_HORIZONTAL_HALO'];hy=config['FP_MACRO_VERTICAL_HALO']
        for master,(width,height,pin_count,spice_name) in dimensions.items():
            lef=(TARGET/'ihp'/(master+'.lef')).read_text()
            size=re.search(r'SIZE\s+([\d.]+)\s+BY\s+([\d.]+)\s*;',lef)
            self.assertEqual(tuple(map(float,size.groups())),(width,height))
            pins=re.findall(r'^\s*PIN\s+(\S+)',lef,re.M)
            self.assertEqual(len(pins),pin_count)
            abstract=[pin for line in (TARGET/spice_name).read_text().splitlines()
                      if line.startswith('+') for pin in line[1:].split()]
            self.assertEqual(set(abstract),set(pins));self.assertEqual(len(abstract),len(pins))
            # Netgen infers named Verilog bus widths from contiguous SPICE
            # ports. Equal pin sets alone miss interleaved/truncated buses.
            buses={}
            for position,pin in enumerate(abstract):
                match=re.fullmatch(r'(.*)\[(\d+)\]',pin)
                if match:buses.setdefault(match[1],[]).append((position,int(match[2])))
            for name,entries in buses.items():
                positions,indices=zip(*entries)
                self.assertEqual(list(positions),list(range(positions[0],positions[0]+len(entries))),name)
                self.assertEqual(list(indices),list(range(len(entries)-1,-1,-1)),name)
            for name,inst in config['MACROS'][master]['instances'].items():
                actual[name]=master;self.assertEqual(inst['orientation'],'N')
                x,y=inst['location'];box=(x-hx,y-hy,x+width+hx,y+height+hy)
                boxes.append(box)
                self.assertGreaterEqual(box[0],2.88);self.assertGreaterEqual(box[1],3.78)
                self.assertLessEqual(box[2],1721.28);self.assertLessEqual(box[3],706.86)
        self.assertEqual(actual,EXPECTED_INSTANCES)
        for i,a in enumerate(boxes):
            for b in boxes[i+1:]:
                self.assertFalse(a[0]<b[2] and b[0]<a[2] and a[1]<b[3] and b[1]<a[3])
        for key in ['ERROR_ON_LVS_ERROR','ERROR_ON_KLAYOUT_DRC','ERROR_ON_TR_DRC']:
            self.assertTrue(config[key])
        self.assertFalse(config['GRT_ALLOW_CONGESTION'])

    def test_active_manifest_and_submission_sources_use_sram(self):
        manifest = (ROOT / 'info.yaml').read_text()
        self.assertIn('top_module: tt_um_wlmoi_igor_neural_sram', manifest)
        self.assertIn('tiles: 8x4', manifest)
        active = json.loads((ROOT / 'src/config.json').read_text())
        fragment = json.loads((TARGET / 'config.fragment.json').read_text())
        self.assertEqual(active['MACROS'], fragment['MACROS'])
        # Tcl consumes escaped '[' in double-quoted config strings. Avoid bank
        # bracket escapes here; the geometry step still enforces all three names.
        for connection in active['PDN_MACRO_CONNECTIONS']:
            pattern = connection.split()[0]
            self.assertNotIn('\\[', pattern)
            self.assertEqual({name for name in EXPECTED_INSTANCES
                              if re.fullmatch(pattern, name)},
                             set(EXPECTED_INSTANCES))
            self.assertIsNone(re.fullmatch(pattern, 'other_store.banks[0].i_sram'))
        for old, new in [('project.v', 'igor_neural_sram_top.v'),
                         ('igor_parameter_sram.v', 'igor_parameter_sram.v'),
                         ('igor_activation_sram.v','igor_activation_sram.v'),
                         ('sram_2048x64_bb.v','sram_2048x64_bb.v'),
                         ('sram_256x16_bb.v','sram_256x16_bb.v')]:
            self.assertEqual((TARGET / old).read_bytes(), (ROOT / 'src' / new).read_bytes())
        active_core = (ROOT / 'src/igor_neural_datapath.v').read_text()
        self.assertEqual((TARGET / 'igor_neural_datapath.v').read_text(), active_core)
        self.assertIn('clock_hz: 50000000', manifest)
        self.assertEqual(active['CLOCK_PERIOD'], 20)
        self.assertEqual(active['CTS_APPLY_NDR'],'root_only')
        self.assertTrue(active['CTS_OBSTRUCTION_AWARE'])

    def powered_fixture(self, parameter_count=1, activation_count=2):
        specs={**{('parameter_store.i_sram' if i==0 else f'parameter_store.extra[{i}].i_sram'):PARAM_MACRO for i in range(parameter_count)},
               **{f'neural.activation_store.banks[{i}].i_sram':ACT_MACRO for i in range(activation_count)}}
        return '\n'.join(master+' \\'+name+' ('
             '.\\VDD! (VPWR), .\\VDDARRAY! (VPWR), .\\VSS! (VGND), .A_DIN(data));'
             for name,master in specs.items())+'\nother_module keep(.\\VDD! (other));'

    def test_lvs_supply_adaptation_is_scoped_to_all_banks(self):
        text=normalize_sram_power_pins(self.powered_fixture())
        for pin in ['VDD!','VDDARRAY!','VSS!']:
            self.assertEqual(text.count('.'+pin+'('),3)
        self.assertIn('other_module keep(.\\VDD! (other));',text)
        escaped=self.powered_fixture().replace('banks[','banks\\[').replace('].i_sram','\\].i_sram')
        self.assertEqual(normalize_sram_power_pins(escaped).count('.VDD!(VPWR)'),3)
        for fixture in [self.powered_fixture(0),self.powered_fixture(2),self.powered_fixture(1,1),
                        self.powered_fixture(1,3),self.powered_fixture().replace(PARAM_MACRO,ACT_MACRO),
                        self.powered_fixture().replace('.\\VDDARRAY! (VPWR)','')]:
            with self.assertRaises(ValueError):normalize_sram_power_pins(fixture)

    def test_lvs_json_preserves_errors_and_original(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'lvs.netgen.json'
            original = '{"identifier":"\\parameter_store.i_sram", "errors":7}'
            path.write_text(original)
            self.assertEqual(repair_report(path), 1)
            self.assertEqual(json.loads(path.read_text())['errors'], 7)
            self.assertEqual(path.with_suffix('.json.original').read_text(), original)
            path.write_text('{"errors":7,}')
            with self.assertRaises(json.JSONDecodeError):
                repair_report(path)


if __name__ == '__main__':
    unittest.main()
