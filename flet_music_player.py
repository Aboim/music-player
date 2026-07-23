import flet as ft
import pygame.mixer
import os
import asyncio
from mutagen.mp3 import MP3
from mutagen.wave import WAVE


class MusicPlayer:
    def __init__(self):
        self.playlist: list[str] = []
        self.current_index = -1
        self._playing = False
        self.is_paused = False
        self.current_duration = 0.0
        self.mixer_initialized = False
        try:
            pygame.mixer.init()
            self.mixer_initialized = True
        except Exception:
            pass

    @property
    def is_playing(self):
        return self._playing

    @property
    def current_file(self):
        if 0 <= self.current_index < len(self.playlist):
            return self.playlist[self.current_index]
        return None

    def get_duration(self, filepath):
        try:
            ext = os.path.splitext(filepath)[1].lower()
            if ext == ".mp3":
                return MP3(filepath).info.length
            elif ext == ".wav":
                return WAVE(filepath).info.length
        except Exception:
            pass
        return 0.0

    def load_and_play(self, index):
        if not self.mixer_initialized:
            return
        if 0 <= index < len(self.playlist):
            self.current_index = index
            self.current_duration = self.get_duration(self.playlist[index])
            pygame.mixer.music.load(self.playlist[index])
            pygame.mixer.music.play()
            self.is_paused = False
            self._playing = True

    def toggle_play_pause(self):
        if not self.mixer_initialized:
            return self.is_playing
        if self._playing and not self.is_paused:
            pygame.mixer.music.pause()
            self.is_paused = True
        elif self.is_paused:
            pygame.mixer.music.unpause()
            self.is_paused = False
        elif self.playlist:
            idx = self.current_index if self.current_index >= 0 else 0
            self.load_and_play(idx)
        return self.is_playing

    def stop(self):
        if self.mixer_initialized:
            pygame.mixer.music.stop()
        self._playing = False
        self.is_paused = False
        self.current_duration = 0.0

    def next(self):
        if self.playlist:
            nxt = (self.current_index + 1) % len(self.playlist)
            self.load_and_play(nxt)

    def prev(self):
        if self.playlist:
            prv = (self.current_index - 1) % len(self.playlist)
            self.load_and_play(prv)

    def get_position(self):
        if not self.mixer_initialized:
            return 0.0
        if self._playing and not self.is_paused:
            pos = pygame.mixer.music.get_pos()
            return pos / 1000.0 if pos >= 0 else 0.0
        return 0.0

    def set_volume(self, vol):
        if self.mixer_initialized:
            pygame.mixer.music.set_volume(vol / 100.0)

    def add_songs(self, files):
        for f in files:
            if f not in self.playlist and os.path.isfile(f):
                self.playlist.append(f)

    def remove_song(self, index):
        if 0 <= index < len(self.playlist):
            was_current = index == self.current_index
            del self.playlist[index]
            if was_current:
                self.stop()
                self.current_index = -1
            elif index < self.current_index:
                self.current_index -= 1

    def clear_playlist(self):
        self.stop()
        self.playlist.clear()
        self.current_index = -1


def main(page: ft.Page):
    page.title = "Music Player"
    page.theme_mode = ft.ThemeMode.DARK
    page.bgcolor = "#0F172A"
    page.window.width = 480
    page.window.height = 700
    page.window.min_width = 380
    page.window.min_height = 550
    page.padding = 20

    page.fonts = {
        "Outfit": (
            "https://fonts.googleapis.com/css2"
            "?family=Outfit:wght@300;400;500;600;700&display=swap"
        )
    }

    player = MusicPlayer()
    progress_task = None
    user_seeking = False

    def format_time(secs):
        if secs <= 0:
            return "00:00"
        m, s = divmod(int(secs), 60)
        return f"{m:02d}:{s:02d}"

    current_track_text = ft.Text(
        "No track playing",
        size=18,
        weight=ft.FontWeight.W_600,
        color="#F8FAFC",
        font_family="Outfit",
        text_align=ft.TextAlign.CENTER,
        max_lines=2,
        overflow=ft.TextOverflow.ELLIPSIS,
    )

    current_time_text = ft.Text(
        "00:00", size=12, color="#94A3B8", font_family="Outfit"
    )
    total_time_text = ft.Text(
        "00:00", size=12, color="#94A3B8", font_family="Outfit"
    )

    progress_slider = ft.Slider(
        min=0,
        max=100,
        value=0,
        active_color="#38BDF8",
        inactive_color="#334155",
        thumb_color="#38BDF8",
        expand=True,
    )

    volume_slider = ft.Slider(
        min=0,
        max=100,
        value=70,
        active_color="#38BDF8",
        inactive_color="#334155",
        thumb_color="#38BDF8",
        width=140,
    )
    volume_text = ft.Text("70%", size=12, color="#94A3B8", font_family="Outfit")

    playlist_view = ft.ListView(expand=True, spacing=4, padding=0)

    file_picker = ft.FilePicker()
    file_picker.on_result = lambda e: on_files_picked(e)
    page.overlay.append(file_picker)

    def make_icon_btn(icon, tooltip, on_click):
        return ft.IconButton(
            icon=icon,
            icon_color="#38BDF8",
            icon_size=28,
            tooltip=tooltip,
            on_click=on_click,
            style=ft.ButtonStyle(
                bgcolor={"": "#1E293B", "hovered": "#334155"},
                shape=ft.RoundedRectangleBorder(radius=8),
            ),
            width=50,
            height=50,
        )

    def refresh_playlist():
        playlist_view.controls.clear()
        for i, fp in enumerate(player.playlist):
            name = os.path.basename(fp)
            active = i == player.current_index
            row = ft.Container(
                content=ft.Row(
                    [
                        ft.Text(
                            name,
                            size=13,
                            color="#38BDF8" if active else "#E2E8F0",
                            font_family="Outfit",
                            expand=True,
                            max_lines=1,
                            overflow=ft.TextOverflow.ELLIPSIS,
                        ),
                        ft.IconButton(
                            icon=ft.Icons.CLOSE,
                            icon_color="#64748B",
                            icon_size=16,
                            tooltip="Remove",
                            data=i,
                            on_click=lambda e: remove_song(e),
                            width=30,
                            height=30,
                        ),
                    ]
                ),
                bgcolor="#0E3A47" if active else "#1E293B",
                border_radius=8,
                padding=ft.Padding(left=12, top=10, right=12, bottom=10),
                on_click=lambda e, idx=i: play_from_list(idx),
            )
            playlist_view.controls.append(row)

        pl_count.value = f"{len(player.playlist)} tracks"
        page.update()

    def update_now_playing():
        f = player.current_file
        current_track_text.value = os.path.basename(f) if f else "No track playing"
        total_time_text.value = format_time(player.current_duration)
        refresh_playlist()

    def on_files_picked(e: ft.FilePickerResultEvent):
        if e.files:
            player.add_songs([f.path for f in e.files])
            refresh_playlist()
            if len(player.playlist) == 1 and not player.is_playing:
                play_from_list(0)

    def play_from_list(idx):
        player.load_and_play(idx)
        player.is_paused = False
        play_btn.icon = ft.Icons.PAUSE
        play_btn.tooltip = "Pause"
        progress_slider.value = 0
        current_time_text.value = "00:00"
        update_now_playing()
        start_progress()

    def remove_song(e):
        idx = e.control.data
        was_current = idx == player.current_index
        player.remove_song(idx)
        if was_current:
            play_btn.icon = ft.Icons.PLAY_ARROW
            play_btn.tooltip = "Play"
            progress_slider.value = 0
            current_time_text.value = "00:00"
            total_time_text.value = "00:00"
        update_now_playing()

    def on_play_pause(e):
        if player._playing and not player.is_paused:
            player.toggle_play_pause()
            play_btn.icon = ft.Icons.PLAY_ARROW
            play_btn.tooltip = "Play"
        elif player.is_paused:
            player.toggle_play_pause()
            play_btn.icon = ft.Icons.PAUSE
            play_btn.tooltip = "Pause"
            start_progress()
        elif player.playlist:
            player.toggle_play_pause()
            play_btn.icon = ft.Icons.PAUSE
            play_btn.tooltip = "Pause"
            progress_slider.value = 0
            current_time_text.value = "00:00"
            update_now_playing()
            start_progress()
        page.update()

    def on_stop(e):
        player.stop()
        play_btn.icon = ft.Icons.PLAY_ARROW
        play_btn.tooltip = "Play"
        progress_slider.value = 0
        current_time_text.value = "00:00"
        update_now_playing()
        page.update()

    def on_next(e):
        if player.playlist:
            player.next()
            play_btn.icon = ft.Icons.PAUSE
            play_btn.tooltip = "Pause"
            progress_slider.value = 0
            current_time_text.value = "00:00"
            update_now_playing()
            start_progress()
            page.update()

    def on_prev(e):
        if player.playlist:
            player.prev()
            play_btn.icon = ft.Icons.PAUSE
            play_btn.tooltip = "Pause"
            progress_slider.value = 0
            current_time_text.value = "00:00"
            update_now_playing()
            start_progress()
            page.update()

    def on_volume_change(e):
        vol = int(e.control.value)
        player.set_volume(vol)
        volume_text.value = f"{vol}%"
        page.update()

    def on_progress_change_start(e):
        if not e or e.control is None:
            return
        nonlocal user_seeking
        user_seeking = True

    def on_progress_change_end(e):
        nonlocal user_seeking
        if player.current_duration > 0 and player._playing:
            seek_secs = (progress_slider.value / 100.0) * player.current_duration
            try:
                pygame.mixer.music.set_pos(seek_secs)
            except Exception:
                pass
        user_seeking = False

    def on_add_files(e):
        file_picker.pick_files(
            allow_multiple=True,
            allowed_extensions=["mp3", "wav", "ogg", "m4a", "flac"],
        )

    def on_clear_all(e):
        player.clear_playlist()
        play_btn.icon = ft.Icons.PLAY_ARROW
        play_btn.tooltip = "Play"
        progress_slider.value = 0
        current_time_text.value = "00:00"
        total_time_text.value = "00:00"
        update_now_playing()
        page.update()

    async def update_progress():
        while True:
            busy = pygame.mixer.music.get_busy() if player.mixer_initialized else False

            if player._playing and not player.is_paused:
                pos = player.get_position()

                if not busy and pos > 0.3:
                    if player.playlist:
                        player.next()
                        play_btn.icon = ft.Icons.PAUSE
                        play_btn.tooltip = "Pause"
                    else:
                        player.stop()
                        play_btn.icon = ft.Icons.PLAY_ARROW
                        play_btn.tooltip = "Play"
                    progress_slider.value = 0
                    current_time_text.value = "00:00"
                    update_now_playing()
                    page.update()
                    continue

                if pos >= 0:
                    current_time_text.value = format_time(pos)
                    if (
                        player.current_duration > 0
                        and not user_seeking
                    ):
                        pct = min(
                            (pos / player.current_duration) * 100, 100
                        )
                        progress_slider.value = pct
                    page.update()

            await asyncio.sleep(0.5)

    def start_progress():
        nonlocal progress_task
        if progress_task:
            progress_task.cancel()
        progress_task = asyncio.ensure_future(update_progress())

    play_btn = make_icon_btn(ft.Icons.PLAY_ARROW, "Play", on_play_pause)

    try:
        progress_slider.on_change_start = on_progress_change_start
        progress_slider.on_change_end = on_progress_change_end
    except Exception:
        pass

    volume_slider.on_change = on_volume_change

    header = ft.Text(
        "MUSIC PLAYER",
        size=24,
        weight=ft.FontWeight.W_700,
        color="#38BDF8",
        font_family="Outfit",
        text_align=ft.TextAlign.CENTER,
    )

    now_playing_card = ft.Container(
        content=ft.Column(
            [
                current_track_text,
                ft.Divider(height=1, color="#334155"),
                ft.Row(
                    [
                        current_time_text,
                        progress_slider,
                        total_time_text,
                    ],
                    alignment=ft.MainAxisAlignment.CENTER,
                    spacing=8,
                ),
            ],
            spacing=12,
        ),
        bgcolor="#1E293B",
        border_radius=12,
        padding=16,
        margin=ft.Margin(bottom=16, left=0, top=0, right=0),
    )

    controls_row = ft.Row(
        [
            make_icon_btn(ft.Icons.SKIP_PREVIOUS, "Previous", on_prev),
            play_btn,
            make_icon_btn(ft.Icons.STOP, "Stop", on_stop),
            make_icon_btn(ft.Icons.SKIP_NEXT, "Next", on_next),
        ],
        alignment=ft.MainAxisAlignment.CENTER,
        spacing=8,
    )

    volume_row = ft.Row(
        [
            ft.Icon(ft.Icons.VOLUME_DOWN, color="#64748B", size=18),
            volume_slider,
            ft.Icon(ft.Icons.VOLUME_UP, color="#64748B", size=18),
            volume_text,
        ],
        alignment=ft.MainAxisAlignment.CENTER,
        spacing=8,
    )

    actions_row = ft.Row(
        [
            ft.Button(
                "Add Music",
                icon=ft.Icons.ADD,
                on_click=on_add_files,
                style=ft.ButtonStyle(
                    bgcolor="#1E293B",
                    color="#38BDF8",
                    shape=ft.RoundedRectangleBorder(radius=8),
                    padding=ft.Padding(left=20, top=12, right=20, bottom=12),
                ),
            ),
            ft.Button(
                "Clear All",
                icon=ft.Icons.DELETE_OUTLINE,
                on_click=on_clear_all,
                style=ft.ButtonStyle(
                    bgcolor="#1E293B",
                    color="#EF4444",
                    shape=ft.RoundedRectangleBorder(radius=8),
                    padding=ft.Padding(left=20, top=12, right=20, bottom=12),
                ),
            ),
        ],
        alignment=ft.MainAxisAlignment.CENTER,
        spacing=12,
    )

    pl_count = ft.Text(
        "0 tracks", size=12, color="#64748B", font_family="Outfit"
    )

    playlist_header = ft.Container(
        content=ft.Row(
            [
                ft.Text(
                    "Playlist",
                    size=14,
                    weight=ft.FontWeight.W_600,
                    color="#94A3B8",
                    font_family="Outfit",
                ),
                pl_count,
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        ),
        padding=ft.Padding(top=12, bottom=4, left=0, right=0),
    )

    page.add(
        ft.Column(
            [
                header,
                now_playing_card,
                controls_row,
                ft.Container(height=8),
                volume_row,
                ft.Container(height=8),
                actions_row,
                playlist_header,
                ft.Container(content=playlist_view, expand=True, border_radius=8),
            ],
            expand=True,
            spacing=0,
            scroll=ft.ScrollMode.HIDDEN,
        )
    )

    player.set_volume(70)
    page.update()

    refresh_playlist()


if __name__ == "__main__":
    ft.run(main)
