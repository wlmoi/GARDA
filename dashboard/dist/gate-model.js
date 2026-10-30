// Behavioral companion for rtl/igor_safety_security_gate.v, not a browser RTL simulator.
export function evaluateGate(state = {}) {
  const s = {rst_n:1,ready:1,estop:0,protective_stop:0,map_ok:1,cfg_ok:1,result_valid:1,all_done:1,arithmetic_fault:0,timeout:0,candidate_v:12,previous_v:12,max_v:20,max_dv:8,candidate_w:4,previous_w:4,max_w:20,max_dw:12,...state};
  const v = Number(s.candidate_v) & 31;
  const prev = Number(s.previous_v) & 31;
  const signed7 = n => ((Number(n) & 127) ^ 64) - 64;
  const w = signed7(s.candidate_w), pw = signed7(s.previous_w);
  const rules = [!s.rst_n,s.estop,s.protective_stop,!s.ready,!s.map_ok,!s.cfg_ok,s.arithmetic_fault,s.timeout,!s.all_done || !s.result_valid,v>(Number(s.max_v)&31) || Math.abs(w)>(Number(s.max_w)&127),Math.abs(v-prev)>(Number(s.max_dv)&31) || Math.abs(w-pw)>(Number(s.max_dw)&127)];
  const fault = rules.findIndex(Boolean) + 1;
  return {motor_enable:fault===0?1:0,v_command:fault===0?v:0,omega_command:fault===0?w:0,fault_code:fault};
}
export const faultDescriptions = ['Semua kondisi valid.','Reset aktif.','Emergency stop aktif.','Protective stop aktif.','Sistem belum ready.','Costmap tidak valid.','Konfigurasi tidak valid.','Fault aritmetika.','Batas waktu terlampaui.','Hasil belum lengkap atau tidak valid.','Perintah melampaui batas v atau omega.','Perubahan perintah melampaui batas delta.'];
