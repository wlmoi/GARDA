# The routed 64-bit SRAM mask has seven-pin branches left directly on two
# minimum-drive NOR decoders. Generic repair buffers the other branches but
# leaves these above the SRAM input transition limit. Upgrade only actual
# mask-net NOR2B drivers, preserving the Boolean function and all connections.
proc jp_repair_mask_drivers {} {
    set block [ord::get_db_block]
    set sram [$block findInst parameter_store.i_sram]
    if {$sram eq "NULL"} {error "Parameter SRAM missing during mask drive repair"}
    set drivers [dict create]
    for {set bit 0} {$bit < 64} {incr bit} {
        set pin [$sram findITerm [format {A_BM[%d]} $bit]]
        if {$pin eq "NULL"} {error "SRAM mask pin $bit missing"}
        set net [$pin getNet]
        if {$net eq "NULL"} {error "SRAM mask pin $bit disconnected"}
        foreach terminal [$net getITerms] {
            if {[$terminal getIoType] eq "OUTPUT"} {
                set driver [$terminal getInst]
                if {[[$driver getMaster] getName] eq "sg13cmos5l_nor2b_1"} {
                    dict set drivers [$driver getName] 1
                }
            }
        }
    }
    foreach name [dict keys $drivers] {
        replace_cell $name sg13cmos5l_nor2b_2
        # Keep the measured drive strength through subsequent timing repair.
        # Cells remain movable for the ordinary detailed-placement step.
        set_dont_touch $name
        puts "SRAM mask driver $name: sg13cmos5l_nor2b_1 -> sg13cmos5l_nor2b_2"
    }
    return [dict size $drivers]
}
