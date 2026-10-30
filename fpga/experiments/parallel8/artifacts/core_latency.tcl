if {[catch {
puts "DISPLAYED [gtkwave::getDisplayedSignals]"
if {[llength [gtkwave::getDisplayedSignals]] != 10} {error "Not all requested signals are displayed"}
gtkwave::setZoomRangeTimes 0 149000000
gtkwave::setMarker 148294000
gtkwave::setNamedMarker A 9970000 "START"
gtkwave::setNamedMarker B 148290000 "DONE"
gtkwave::/File/Grab_To_File {D:/LinkedinProjects/igor_ws/igor_ws/fpga/experiments/parallel8/artifacts/core_latency.png}
gtkwave::/File/Quit
} capture_error]} {
puts stderr $capture_error
exit 1
}
