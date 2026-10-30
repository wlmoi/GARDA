if {[catch {
puts "DISPLAYED [gtkwave::getDisplayedSignals]"
if {[llength [gtkwave::getDisplayedSignals]] != 12} {error "Not all requested signals are displayed"}
gtkwave::setZoomRangeTimes 2930871000 2931191000
gtkwave::setMarker 2931031000
gtkwave::/File/Grab_To_File {D:/LinkedinProjects/igor_ws/igor_ws/fpga/evidence/visual_review/02_planner_invalid_map.png}
gtkwave::/File/Quit
} capture_error]} {
puts stderr $capture_error
exit 1
}
