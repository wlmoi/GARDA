# SPDX-License-Identifier: Apache-2.0
# Read column positions from the installed macro, including its irregular middle
# band. Both the PDN generator and the extension step use this geometry.
proc jp_find_sram {name} {
    set block [ord::get_db_block]
    set inst [$block findInst $name]
    if {$inst != "NULL"} { return $inst }
    # OpenSTA/OpenDB preserve escapes around generate-array brackets, whereas
    # the RTL and MACROS configuration use canonical Verilog hierarchy names.
    set escaped [string map [list {[} {\[} {]} {\]}] $name]
    return [$block findInst $escaped]
}

proc jp_column_clears_signal_pins {center} {
    set block [ord::get_db_block]
    # 2.1 um stripe plus 0.5 um clearance on each side. M4.b requires 0.21 um.
    set left [expr {$center - 1550}]
    set right [expr {$center + 1550}]
    foreach term [$block getBTerms] {
        if {[$term getSigType] in {POWER GROUND}} { continue }
        foreach pin [$term getBPins] {
            foreach box [$pin getBoxes] {
                if {[[$box getTechLayer] getName] != "Metal4"} { continue }
                if {$left < [$box xMax] && $right > [$box xMin]} { return 0 }
            }
        }
    }
    return 1
}

proc jp_one_sram_columns {inst} {
    set block [ord::get_db_block]
    # Classic normally applies the template after PDN generation. This design
    # applies it first so both regular and SRAM columns see the real pin bank.
    foreach term [$block getBTerms] {
        if {[$term getSigType] in {POWER GROUND}} { continue }
        set placed 0
        foreach pin [$term getBPins] {
            if {[$pin getPlacementStatus] in {PLACED FIRM LOCKED} &&
                [llength [$pin getBoxes]] > 0} { set placed 1 }
        }
        if {!$placed} {
            error "Signal pin [$term getName] requires template placement before PDN generation"
        }
    }
    if {$inst == "NULL"} { error "Neural SRAM instance required" }
    if {[$inst getOrient] != "R0"} { error "Program SRAM requires N orientation" }
    if {[[$inst getMaster] getName] ni {RM_IHPSG13_1P_2048x64_c2_bm_bist RM_IHPSG13_1P_256x16_c2_bm_bist}} {
        error "Unexpected program SRAM master"
    }
    set origin [$inst getOrigin]
    set columns [dict create]
    foreach pin {VDD! VDDARRAY! VSS!} {
        set term [$inst findITerm $pin]
        set net [$term getNet]
        if {$net == "NULL"} { error "Unconnected SRAM supply $pin" }
        set expected [expr {$pin == "VSS!" ? $::env(GND_NET) : $::env(VDD_NET)}]
        if {[$net getName] != $expected} { error "Incorrect SRAM supply $pin" }
        foreach port [[$term getMTerm] getMPins] {
            foreach box [$port getGeometry] {
                if {[[$box getTechLayer] getName] != "Metal4"} {
                    error "Unexpected SRAM supply layer"
                }
                if {[$box xMax] - [$box xMin] < 2100} { error "SRAM column too narrow" }
                set center [expr {[lindex $origin 0] + ([$box xMin] + [$box xMax]) / 2}]
                if {[dict exists $columns $center] && [dict get $columns $center] != $expected} {
                    error "Conflicting SRAM supplies"
                }
                dict set columns $center $expected
            }
        }
    }
    set expected_columns [expr {[[$inst getMaster] getName] == "RM_IHPSG13_1P_2048x64_c2_bm_bist" ? 136:40}]
    if {[dict size $columns] != $expected_columns} { error "Unexpected SRAM power-column count" }
    dict for {center net} $columns {
        if {![jp_column_clears_signal_pins $center]} {
            error "SRAM supply column at $center overlaps a Metal4 signal-pin corridor. Move the SRAM outside the I/O pin bank."
        }
    }
    return $columns
}

# One packed parameter and two activation banks. Never extend
# a column across another macro unless that macro has the same rail at that x.
proc jp_sram_specs {} {
    set result [dict create]
    dict set result parameter_store.i_sram RM_IHPSG13_1P_2048x64_c2_bm_bist
    for {set b 0} {$b < 2} {incr b} {
        dict set result [format {neural.activation_store.banks[%d].i_sram} $b] RM_IHPSG13_1P_256x16_c2_bm_bist
    }
    return $result
}
proc jp_sram_columns {} {
    set block [ord::get_db_block]
    if {[$block getDbUnitsPerMicron] != 1000} { error "Expected 1000 DBU/um" }
    set columns [dict create]
    set expected [dict create]
    set die [$block getDieArea]
    dict for {name master} [jp_sram_specs] {
        set inst [jp_find_sram $name]
        if {$inst == "NULL"} { error "Missing SRAM $name" }
        if {[[$inst getMaster] getName] != $master} { error "Incorrect SRAM master for $name" }
        if {[$inst getPlacementStatus] ni {PLACED FIRM LOCKED}} { error "Unplaced SRAM $name" }
        set box [$inst getBBox]
        if {[$box xMin] < [$die xMin] || [$box xMax] > [$die xMax] ||
            [$box yMin] < [$die yMin] || [$box yMax] > [$die yMax]} {
            error "SRAM $name exceeds approved die bounds"
        }
        set local [jp_one_sram_columns $inst]
        dict set expected $name $local
        dict for {center net} $local {
            if {[dict exists $columns $center] && [dict get $columns $center] != $net} {
                error "Conflicting supplies between SRAM banks at $center"
            }
            dict set columns $center $net
        }
    }
    set count 0
    foreach inst [$block getInsts] {
        if {[[$inst getMaster] getName] in {RM_IHPSG13_1P_2048x64_c2_bm_bist RM_IHPSG13_1P_256x16_c2_bm_bist}} { incr count }
    }
    if {$count != 3} { error "Expected exactly 3 physical SRAM instances" }
    dict for {name local} $expected {
        set box [[jp_find_sram $name] getBBox]
        dict for {center net} $columns {
            if {$center >= [$box xMin] - 1550 && $center <= [$box xMax] + 1550} {
                if {![dict exists $local $center] || [dict get $local $center] != $net} {
                    error "SRAM column at $center crosses incompatible bank $name"
                }
            }
        }
    }
    return $columns
}
