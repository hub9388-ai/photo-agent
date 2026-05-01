import unittest

import photo_v1
from photo_events import BufferEventSink


class EventTests(unittest.TestCase):
    def test_print_streaming_can_write_into_buffer_sink(self) -> None:
        sink = BufferEventSink()

        photo_v1._print_streaming("alpha\nbeta", line_delay=0, char_delay=0, sink=sink)

        self.assertEqual(sink.text, "alpha\nbeta\n")


if __name__ == "__main__":
    unittest.main()
