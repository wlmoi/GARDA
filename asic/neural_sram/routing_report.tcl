# Preserve LibreLane's ordinary routing, antenna handling and error checks.
# Add coordinates to its congestion report, including failed attempts.
rename global_route jp_original_global_route
proc global_route {args} {
    if {[lsearch -exact $args -congestion_report_file] < 0} {
        set report [file join [file dirname $::env(SAVE_ODB)] congestion.rpt]
        lappend args -congestion_report_file $report -congestion_report_iter_step 10
        puts "Saving routing congestion locations to $report"
    }
    return [jp_original_global_route {*}$args]
}
source $::env(SCRIPTS_DIR)/openroad/grt.tcl
