if {[catch {
puts "DISPLAYED [gtkwave::getDisplayedSignals]"
if {[llength [gtkwave::getDisplayedSignals]] != 13} {error "Not all requested signals are displayed"}
gtkwave::setZoomRangeTimes 4759771000 4760091000
gtkwave::setMarker 4759931000
gtkwave::/File/Grab_To_File {D:/LinkedinProjects/igor_ws/igor_ws/fpga/evidence/visual_review/06_planner_map_version.png}
gtkwave::/File/Quit
} capture_error]} {
puts stderr $capture_error
exit 1
}
