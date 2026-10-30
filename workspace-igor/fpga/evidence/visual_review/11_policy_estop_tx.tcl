if {[catch {
puts "DISPLAYED [gtkwave::getDisplayedSignals]"
if {[llength [gtkwave::getDisplayedSignals]] != 13} {error "Not all requested signals are displayed"}
gtkwave::setZoomRangeTimes 7530670999 7536670999
gtkwave::setMarker 7533670999
gtkwave::/File/Grab_To_File {D:/LinkedinProjects/igor_ws/igor_ws/fpga/evidence/visual_review/11_policy_estop_tx.png}
gtkwave::/File/Quit
} capture_error]} {
puts stderr $capture_error
exit 1
}
