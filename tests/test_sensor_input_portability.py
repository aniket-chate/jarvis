from perception.channels import sensor_input


def test_sensor_channel_reports_unavailable_when_windows_apis_are_missing(monkeypatch):
    monkeypatch.setattr(sensor_input, "win32gui", None)
    monkeypatch.setattr(sensor_input, "win32process", None)

    result = sensor_input.SensorInputChannel().get_active_application()

    assert result == {
        "window_title": "Unavailable on this platform",
        "process_name": "unsupported",
    }


def test_sensor_idle_time_degrades_safely_without_windows_api():
    channel = sensor_input.SensorInputChannel()

    # ctypes.windll is not present on Linux/macOS; the channel must not crash.
    assert channel.get_system_idle_seconds() >= 0.0
