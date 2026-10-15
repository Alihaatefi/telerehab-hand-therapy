"""The Qt widgets, built for real and drawn offscreen.

No window is ever shown: widgets are rendered into images, which is enough to
catch the failures that matter here - an exception while painting, a control
that cannot hold a value, an icon that does not exist.
"""
from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

import itertools

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QImage, QPainter

from telerehab.api.models import GameMode, Session
from telerehab.reports import metric_series
from telerehab.ui import art, icons, theme
from telerehab.ui.charts import LineChart, nice_ticks, write_report_pdf
from telerehab.ui.pages.session import GameStage
from telerehab.ui.widgets import (
    Avatar,
    Banner,
    CameraView,
    Pill,
    ProgressRing,
    SpinField,
    Stepper,
    TextField,
    button,
)

pytestmark = pytest.mark.ui


@pytest.fixture(autouse=True)
def themed(qapp):
    theme.apply_theme(qapp)


def render(widget, width=640, height=400) -> QImage:
    widget.resize(width, height)
    return widget.grab().toImage()


def distinct_colours(image: QImage, step: int = 7) -> int:
    seen = set()
    for x in range(0, image.width(), step):
        for y in range(0, image.height(), step):
            seen.add(image.pixel(x, y))
    return len(seen)


def sessions(count=6, mode=GameMode.TIME_SCORE) -> list[Session]:
    out = []
    for i in range(count):
        if mode is GameMode.TIME_SCORE:
            metrics = {"score": 4.0 + i * 2, "gain": 1.0, "exercise_seconds": 60.0, "movements": 20.0 + i}
        else:
            metrics = {"open_seconds": 5.0, "close_seconds": 5.0, "repetitions": 10.0,
                       "completed_repetitions": 3.0 + i}
        out.append(Session(
            patient_id=1, mode=mode, metrics=metrics, report_id=10 + i,
            timestamp=f"2026-09-{(i * 5) % 27 + 1:02d}T09:00:00.000Z",
        ))
    return sorted(out, key=lambda s: s.timestamp)


# -- inputs -----------------------------------------------------------------------------


class TestSpinField:
    def test_shows_its_value(self, qtbot):
        field = SpinField(minimum=5, maximum=600, value=60, suffix="s")
        qtbot.addWidget(field)
        field.resize(190, 54)
        field.show()
        assert field._edit.text() == "60"
        assert field._edit.width() > 30  # a styled QSpinBox collapsed this to a sliver

    def test_plus_and_minus_step(self, qtbot):
        field = SpinField(minimum=5, maximum=600, value=60, step=5)
        qtbot.addWidget(field)
        seen = []
        field.valueChanged.connect(seen.append)

        field._plus.click()
        field._minus.click()
        field._minus.click()
        assert field.value() == 55
        assert seen == [65.0, 60.0, 55.0]

    def test_the_value_is_clamped_into_range(self, qtbot):
        field = SpinField(minimum=5, maximum=600, value=60)
        qtbot.addWidget(field)

        field._edit.setText("9999")
        field._edit.editingFinished.emit()
        assert field.value() == 600

        field._edit.setText("2")
        field._edit.editingFinished.emit()
        assert field.value() == 5

    def test_buttons_stop_at_the_bounds(self, qtbot):
        field = SpinField(minimum=0.1, maximum=5.0, value=1.0, step=0.1, decimals=1)
        qtbot.addWidget(field)
        for _ in range(80):
            field._plus.click()
        assert field.value() == 5.0
        for _ in range(80):
            field._minus.click()
        assert field.value() == 0.1

    def test_decimals_are_rounded_and_typed_correctly(self, qtbot):
        field = SpinField(minimum=0.1, maximum=5.0, value=1.0, step=0.1, decimals=1)
        qtbot.addWidget(field)
        field.setValue(0.34)
        assert field.value() == 0.3 and isinstance(field.value(), float)
        assert field._edit.text() == "0.3"

    def test_integer_fields_return_integers(self, qtbot):
        field = SpinField(minimum=1, maximum=9, value=3)
        qtbot.addWidget(field)
        assert isinstance(field.value(), int)

    def test_garbage_keeps_the_previous_value(self, qtbot):
        field = SpinField(minimum=1, maximum=9, value=3)
        qtbot.addWidget(field)
        field._edit.setText("")
        field._edit.editingFinished.emit()
        assert field.value() == 3


class TestTextField:
    def test_an_error_marks_the_input_and_clears_when_typing(self, qtbot):
        field = TextField("Patient ID", digits_only=True)
        qtbot.addWidget(field)

        field.set_error("Enter a numeric patient ID")
        assert field.edit.property("invalid") is True
        assert not field._error.isHidden()

        field.edit.setText("4")
        assert field.edit.property("invalid") is False
        assert field._error.isHidden()

    def test_digits_only_rejects_letters(self, qtbot):
        from PySide6.QtTest import QTest

        field = TextField("Patient ID", digits_only=True)
        qtbot.addWidget(field)
        field.show()
        field.edit.setFocus()
        QTest.keyClicks(field.edit, "a1b2")
        assert field.text() == "12"

    def test_text_is_stripped(self, qtbot):
        field = TextField("Name")
        qtbot.addWidget(field)
        field.setText("  Ali  ")
        assert field.text() == "Ali"


# -- small widgets ------------------------------------------------------------------------------


class TestStatusWidgets:
    def test_pill_kinds_set_the_style_property(self, qtbot):
        pill = Pill("ok", "success")
        qtbot.addWidget(pill)
        assert pill.property("pill") == "success"
        pill.set("bad", "danger")
        assert pill.text() == "bad" and pill.property("pill") == "danger"

    def test_every_banner_kind_renders(self, qtbot):
        for kind in ("info", "success", "warning", "danger"):
            banner = Banner("Something happened.", kind)
            qtbot.addWidget(banner)
            assert distinct_colours(render(banner, 400, 60), 3) > 3

    def test_an_unknown_banner_kind_is_an_error(self, qtbot):
        banner = Banner("x", "info")
        qtbot.addWidget(banner)
        with pytest.raises(KeyError):
            banner.set("x", "shouting")

    @pytest.mark.parametrize(
        ("name", "initials"),
        [("Ali Hatefi", "AH"), ("madonna", "M"), ("", "?"), ("  a  b  c ", "AB")],
    )
    def test_avatar_initials(self, qtbot, name, initials):
        avatar = Avatar(name)
        qtbot.addWidget(avatar)
        assert avatar.text() == initials

    def test_progress_ring_clamps_and_paints(self, qtbot):
        ring = ProgressRing(120, 10)
        qtbot.addWidget(ring)
        for value in (-1.0, 0.0, 0.4, 1.0, 7.0):
            ring.set_value(value)
            ring.set_text("3", "seconds left")
            assert distinct_colours(render(ring, 120, 120), 3) > 2
        ring.set_value(7.0)
        assert ring._value == 1.0

    def test_stepper_paints_every_state(self, qtbot):
        stepper = Stepper(["Setup", "Calibrate", "Exercise", "Results"])
        qtbot.addWidget(stepper)
        for index in range(4):
            stepper.set_current(index)
            assert distinct_colours(render(stepper, 700, 40), 3) > 3

    def test_buttons_take_variants_and_icons(self, qtbot):
        for variant in (None, "primary", "danger", "ghost", "onDark"):
            widget = button("Go", variant, icon="play")
            qtbot.addWidget(widget)
            assert not widget.icon().isNull()
            assert widget.property("variant") == variant


# -- icons --------------------------------------------------------------------------------------


class TestIcons:
    def test_every_glyph_renders_something(self, qapp):
        for name in icons.names():
            pixmap = icons.pixmap(name, "#102030", 24)
            assert not pixmap.isNull(), name
            image = pixmap.toImage()
            assert any(image.pixelColor(x, y).alpha() for x in range(image.width()) for y in range(image.height())), name

    def test_an_unknown_icon_is_an_error_not_a_blank(self, qapp):
        with pytest.raises(KeyError):
            icons.pixmap("no-such-icon")

    def test_colour_is_applied(self, qapp):
        image = icons.pixmap("check", "#FF0000", 32, stroke=3).toImage()
        reds = [
            image.pixelColor(x, y) for x in range(image.width()) for y in range(image.height())
            if image.pixelColor(x, y).alpha() > 200
        ]
        assert reds and all(c.red() > 200 and c.green() < 60 for c in reds)

    def test_the_logo_renders(self, qapp):
        assert not icons.logo(64).isNull()


# -- charts ----------------------------------------------------------------------------------------


class TestNiceTicks:
    @pytest.mark.parametrize("top", [0.4, 1, 4.3, 15, 16.2, 59, 100, 1234])
    def test_ticks_start_at_zero_cover_the_data_and_are_evenly_spaced(self, top):
        ticks = nice_ticks(top)
        assert ticks[0] == 0
        assert ticks[-1] >= top
        gaps = {round(b - a, 9) for a, b in itertools.pairwise(ticks)}
        assert len(gaps) == 1

    def test_nothing_to_show_still_gives_an_axis(self):
        assert nice_ticks(0) == [0.0, 1.0]
        assert nice_ticks(-5) == [0.0, 1.0]


class TestLineChart:
    def test_one_pixel_position_per_session(self, qapp):
        series = metric_series(sessions(6), "score")
        chart = LineChart()
        chart.set_series(series)

        image = QImage(640, 320, QImage.Format.Format_ARGB32)
        image.fill(Qt.GlobalColor.white)
        painter = QPainter(image)
        points = chart.paint_to(painter, QRectF(0, 0, 640, 320))
        painter.end()

        assert len(points) == 6
        assert all(isinstance(p, QPointF) for p in points)
        xs = [p.x() for p in points]
        assert xs == sorted(xs)  # time runs left to right
        ys = [p.y() for p in points]
        assert ys == sorted(ys, reverse=True)  # scores rise, so pixel y falls

    def test_points_are_spaced_by_real_time(self, qapp):
        uneven = []
        for day, score in ((1, 3), (2, 4), (3, 5), (28, 9)):  # a long gap at the end
            uneven.append(Session(
                patient_id=1, mode=GameMode.TIME_SCORE,
                metrics={"score": float(score), "gain": 1.0, "exercise_seconds": 60.0, "movements": 1.0},
                report_id=day, timestamp=f"2026-09-{day:02d}T09:00:00.000Z",
            ))
        chart = LineChart()
        chart.set_series(metric_series(uneven, "score"))
        image = QImage(640, 320, QImage.Format.Format_ARGB32)
        painter = QPainter(image)
        points = chart.paint_to(painter, QRectF(0, 0, 640, 320))
        painter.end()

        early_gap = points[1].x() - points[0].x()
        late_gap = points[3].x() - points[2].x()
        assert late_gap > 10 * early_gap

    def test_the_widget_draws_and_survives_hovering(self, qtbot):
        chart = LineChart()
        qtbot.addWidget(chart)
        chart.set_series(metric_series(sessions(5), "score"))
        assert distinct_colours(render(chart, 640, 320), 3) > 5

        chart.resize(640, 320)
        chart.show()
        chart.grab()  # lays out the points
        qtbot.mouseMove(chart, chart._points[2].toPoint())
        assert chart._hover == 2
        assert distinct_colours(render(chart, 640, 320), 3) > 5

    def test_no_series_draws_a_message_not_an_error(self, qtbot):
        chart = LineChart()
        qtbot.addWidget(chart)
        chart.set_series(None)
        image = QImage(400, 200, QImage.Format.Format_ARGB32)
        painter = QPainter(image)
        assert chart.paint_to(painter, QRectF(0, 0, 400, 200)) == []
        painter.end()

    def test_a_single_session_still_draws(self, qtbot):
        chart = LineChart()
        qtbot.addWidget(chart)
        chart.set_series(metric_series(sessions(1), "score"))
        image = QImage(400, 200, QImage.Format.Format_ARGB32)
        painter = QPainter(image)
        points = chart.paint_to(painter, QRectF(0, 0, 400, 200))
        painter.end()
        assert len(points) == 1


class TestPdfReport:
    def test_writes_a_pdf(self, qapp, tmp_path):
        both = sessions(5) + sessions(4, GameMode.OPEN_CLOSE)
        path = write_report_pdf(both, tmp_path / "report.pdf", patient_name="Ali Hatefi")
        data = path.read_bytes()
        assert data.startswith(b"%PDF")
        assert len(data) > 5_000

    def test_a_long_history_paginates_instead_of_failing(self, qapp, tmp_path):
        history = sessions(60) + sessions(60, GameMode.OPEN_CLOSE)
        path = write_report_pdf(history, tmp_path / "long.pdf", patient_name="Long History")
        assert path.read_bytes().count(b"/Type /Page\n") + path.read_bytes().count(b"/Type /Page ") >= 2


# -- scene art ------------------------------------------------------------------------------------------


class TestArt:
    def paint(self, draw, width=800, height=500) -> QImage:
        image = QImage(width, height, QImage.Format.Format_ARGB32)
        image.fill(Qt.GlobalColor.white)
        painter = QPainter(image)
        draw(painter)
        painter.end()
        return image

    def test_the_scene_fills_the_whole_rectangle(self, qapp):
        image = self.paint(lambda p: art.draw_scene(p, QRectF(0, 0, 800, 500)))
        assert distinct_colours(image) > 20
        assert image.pixelColor(2, 2).name() != "#ffffff"  # sky, not bare canvas
        assert image.pixelColor(795, 495).name() != "#ffffff"  # meadow

    @pytest.mark.parametrize("alert", [False, True])
    @pytest.mark.parametrize("flap", [0.0, 1.0, 1.57, 3.14])
    def test_butterfly_at_every_wing_position(self, qapp, flap, alert):
        image = self.paint(lambda p: art.draw_butterfly(p, QPointF(200, 150), 160, flap, 8, alert=alert), 400, 300)
        assert distinct_colours(image, 3) > 8

    @pytest.mark.parametrize("bloom", [0.0, 0.08, 0.5, 1.0])
    def test_flower_from_bud_to_bloom(self, qapp, bloom):
        image = self.paint(
            lambda p: art.draw_flower(p, QPointF(150, 100), 100, bloom=bloom, glow=0.6, stem_to=280),
            300, 300,
        )
        assert distinct_colours(image, 3) > 6

    def test_the_bud_and_the_bloom_look_different(self, qapp):
        bud = self.paint(lambda p: art.draw_flower(p, QPointF(150, 150), 100, bloom=0.0), 300, 300)
        bloom = self.paint(lambda p: art.draw_flower(p, QPointF(150, 150), 100, bloom=1.0), 300, 300)
        assert bud != bloom

    @pytest.mark.parametrize("kind", ["time_score", "open_close"])
    def test_emblems(self, qapp, kind):
        image = self.paint(lambda p: art.draw_emblem(p, QRectF(0, 0, 480, 150), kind), 480, 150)
        assert distinct_colours(image, 3) > 20


class TestGameStage:
    def test_paints_every_state_without_error(self, qtbot):
        stage = GameStage()
        qtbot.addWidget(stage)
        stage.resize(900, 560)

        for settings in (
            dict(),
            dict(dwell=0.6),
            dict(alert=True),
            dict(bloom=0.05),
            dict(paused=True),
            dict(banner="3"),
        ):
            stage.target_x, stage.flower_x = 400.0, 600.0
            stage.dwell, stage.alert, stage.paused, stage.banner, stage.bloom = 0.0, False, False, None, 1.0
            for key, value in settings.items():
                setattr(stage, key, value)
            assert distinct_colours(stage.grab().toImage(), 11) > 10, settings

    def test_the_butterfly_eases_towards_its_target(self, qtbot):
        stage = GameStage()
        qtbot.addWidget(stage)
        stage.target_x = 700.0
        stage._last -= 0.05
        stage._tick()
        assert 0 < stage._x < 700.0

    def test_the_background_is_cached_per_size(self, qtbot):
        stage = GameStage()
        qtbot.addWidget(stage)
        stage.resize(800, 500)
        first = stage._scene()
        assert stage._scene() is first
        stage.resize(900, 520)
        assert stage._scene() is not first


class TestCameraView:
    def test_shows_a_message_in_place_of_video(self, qtbot):
        view = CameraView()
        qtbot.addWidget(view)
        view.set_message("Camera unavailable\ncould not open camera 0")
        assert distinct_colours(render(view, 480, 360), 5) > 3

    def test_draws_a_frame_and_the_hand_over_it(self, qtbot):
        pytest.importorskip("mediapipe")
        from telerehab.vision.demo import DemoTracker

        demo = DemoTracker(realtime=False)
        demo.set_openness(0.9)
        view = CameraView()
        qtbot.addWidget(view)
        view.set_sample(demo.read())
        with_hand = render(view, 480, 360)

        demo.hide_hand(True)
        view.set_sample(demo.read())
        without_hand = render(view, 480, 360)

        assert distinct_colours(with_hand, 3) > 10
        assert with_hand != without_hand
