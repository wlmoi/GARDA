if {[catch {
puts "DISPLAYED [gtkwave::getDisplayedSignals]"
if {[llength [gtkwave::getDisplayedSignals]] != 13} {error "Not all requested signals are displayed"}
gtkwave::setZoomRangeTimes 12462730999 12468730999
gtkwave::setMarker 12465730999
gtkwave::/File/Grab_To_File {D:/LinkedinProjects/igor_ws/igor_ws/fpga/evidence/visual_review/12_policy_stale.png}
gtkwave::/File/Quit
} capture_error]} {
puts stderr $capture_error
exit 1
}
