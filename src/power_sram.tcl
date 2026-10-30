# SPDX-License-Identifier: Apache-2.0
source $::env(SCRIPTS_DIR)/openroad/common/io.tcl
read_current_odb
# Each LibreLane step starts a new process. Resolve supplies again before
# inspecting the saved grid or checking the extended macro connections.
source $::env(SCRIPTS_DIR)/openroad/common/set_power_nets.tcl
source $::env(PROGRAM_SRAM_GEOMETRY)
set block [ord::get_db_block]
set die [$block getDieArea]
set layer [[ord::get_db_tech] findLayer Metal4]
set columns [jp_sram_columns]
set wires [dict create]
foreach name [list $::env(VDD_NET) $::env(GND_NET)] {
    set net [$block findNet $name]
    dict set wires $name [odb::dbSWire_create $net ROUTED]
}
dict for {center name} $columns {
    set left [expr {$center - 1050}]
    set right [expr {$center + 1050}]
    odb::dbSBox_create [dict get $wires $name] $layer \
        $left [$die yMin] $right [$die yMax] STRIPE
    set term [$block findBTerm $name]
    if {$term == "NULL"} { error "Supply boundary pin required" }
    set pin [odb::dbBPin_create $term]
    $pin setPlacementStatus FIRM
    odb::dbBox_create $pin $layer $left [$die yMin] $right [$die yMax]
}
# Connectivity errors stop the flow. These checks include the macro supplies.
foreach name [list $::env(VDD_NET) $::env(GND_NET)] {
    check_power_grid -net $name
    # Replace the pre-extension metric only after this net passes its check.
    utl::metric_integer "design__power_grid_violation__count__net:$name" 0
}
utl::metric_integer design__power_grid_violation__count 0
puts "Program SRAM: extended 40 LEF-derived supply columns to tile boundaries"
write_views
