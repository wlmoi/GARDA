# LibreLane places custom configuration in this Tcl file rather than in the
# initial process environment. Load it before reading the custom script path.
source $::env(_TCL_ENV_IN)
source $::env(NEURAL_SRAM_MASK_REPAIR)

# Run the pinned LibreLane repair flow unchanged, adding the targeted resize
# before its normal legalization, re-routing, and saved netlist/database views.
rename repair_design jp_original_repair_design
proc repair_design {args} {
    set result [jp_original_repair_design {*}$args]
    puts "Upgraded [jp_repair_mask_drivers] SRAM mask decoder drivers"
    return $result
}
source $::env(SCRIPTS_DIR)/openroad/repair_design_postgrt.tcl
