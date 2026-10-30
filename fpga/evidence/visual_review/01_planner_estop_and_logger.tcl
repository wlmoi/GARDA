if {[catch {
puts "DISPLAYED [gtkwave::getDisplayedSignals]"
if {[llength [gtkwave::getDisplayedSignals]] != 10} {error "Not all requested signals are displayed"}
gtkwave::setZoomRangeTimes 814391000 814711000
gtkwave::setMarker 814551000
gtkwave::setNamedMarker A 814535000 "E_STOP_ZERO"
gtkwave::setNamedMarker B 814551000 "LOGGED"
gtkwave::/File/Grab_To_File {D:/LinkedinProjects/igor_ws/igor_ws/fpga/evidence/visual_review/01_planner_estop_and_logger.png}
gtkwave::/File/Quit
} capture_error]} {
puts stderr $capture_error
exit 1
}
