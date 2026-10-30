# SPDX-License-Identifier: Apache-2.0
# Read column positions from the installed macro, including its irregular middle
# band. Both the PDN generator and the extension step use this geometry.
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

proc jp_sram_columns {} {
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
    set inst [$block findInst program_store.i_sram]
    if {$inst == "NULL"} { error "Program SRAM instance required" }
    if {[$inst getOrient] != "R0"} { error "Program SRAM requires N orientation" }
    if {[[$inst getMaster] getName] != "RM_IHPSG13_1P_256x16_c2_bm_bist"} {
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
    if {[dict size $columns] != 40} { error "Expected 20 power and 20 ground columns" }
    dict for {center net} $columns {
        if {![jp_column_clears_signal_pins $center]} {
            error "SRAM supply column at $center overlaps a Metal4 signal-pin corridor. Move the SRAM outside the I/O pin bank."
        }
    }
    return $columns
}
