"""Physical SRAM identities required in synthesis, LVS, and reachable layout."""
PARAM_MACRO='RM_IHPSG13_1P_2048x64_c2_bm_bist'
ACT_MACRO='RM_IHPSG13_1P_256x16_c2_bm_bist'
EXPECTED_INSTANCES={'parameter_store.i_sram':PARAM_MACRO,
                    **{f'neural.activation_store.banks[{i}].i_sram':ACT_MACRO for i in range(2)}}
EXPECTED_COUNTS={PARAM_MACRO:1,ACT_MACRO:2}
