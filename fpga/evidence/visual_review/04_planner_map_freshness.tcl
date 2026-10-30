if {[catch {
puts "DISPLAYED [gtkwave::getDisplayedSignals]"
if {[llength [gtkwave::getDisplayedSignals]] != 12} {error "Not all requested signals are displayed"}
gtkwave::setZoomRangeTimes 3945331000 3945651000
gtkwave::setMarker 3945491000
gtkwave::/File/Grab_To_File {D:/LinkedinProjects/igor_ws/igor_ws/fpga/evidence/visual_review/04_planner_map_freshness.png}
gtkwave::/File/Quit
} capture_error]} {
puts stderr $capture_error
exit 1
}
