if {[catch {
puts "DISPLAYED [gtkwave::getDisplayedSignals]"
if {[llength [gtkwave::getDisplayedSignals]] != 12} {error "Not all requested signals are displayed"}
gtkwave::setZoomRangeTimes 3945371000 3945691000
gtkwave::setMarker 3945531000
gtkwave::/File/Grab_To_File {D:/LinkedinProjects/igor_ws/igor_ws/fpga/evidence/visual_review/05_planner_result_lease.png}
gtkwave::/File/Quit
} capture_error]} {
puts stderr $capture_error
exit 1
}
