import json
import math
import random
from pathlib import Path

# pyrefly: ignore [missing-import]
import pygame


pygame.init()
pygame.display.set_caption("Neon Snake")

WIDTH, HEIGHT = 960, 640
FPS = 60

# --- Board / grid -----------------------------------------------------
# IMPORTANT: the board rect and CELL size must divide evenly so the grid
# is made of *square* cells that exactly tile the panel. Using one
# GRID_SIZE for both axes on a non-square panel (the original bug) lets
# the snake/apple be placed at grid positions that fall outside the
# visible panel. 24px cells divide both 864 and 456 exactly.
BOARD_RECT = pygame.Rect(48, 128, 864, 456)
CELL = 24
GRID_COLS = BOARD_RECT.width // CELL   # 36
GRID_ROWS = BOARD_RECT.height // CELL  # 19

HIGH_SCORE_FILE = Path(__file__).with_name("snake_highscore.json")

BACKGROUND = (8, 12, 28)
BACKGROUND_2 = (24, 12, 45)
PANEL = (21, 25, 52)
PANEL_LIGHT = (43, 42, 84)
SHADOW = (4, 6, 12)
TEXT = (238, 244, 255)
MUTED = (175, 164, 215)
ACCENT = (66, 245, 206)
ACCENT_DARK = (18, 151, 139)
ACCENT_GLOW = (66, 245, 206)
APPLE = (255, 91, 126)
APPLE_DARK = (180, 26, 76)
APPLE_GLOW = (255, 91, 126)
GOLD = (255, 220, 92)


def load_high_score():
    try:
        data = json.loads(HIGH_SCORE_FILE.read_text(encoding="utf-8"))
        return max(0, int(data.get("high_score", 0)))
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return 0


def save_high_score(score):
    try:
        HIGH_SCORE_FILE.write_text(
            json.dumps({"high_score": int(score)}),
            encoding="utf-8",
        )
    except OSError:
        pass


def font(size, bold=False):
    for name in ("tahoma", "Tahoma", "arial", "bahnschrift"):
        f = pygame.font.SysFont(name, size, bold=bold)
        if f:
            return f
    return pygame.font.SysFont(None, size, bold=bold)


def draw_text(
    surface,
    text,
    position,
    size,
    color=TEXT,
    bold=False,
    anchor="topleft",
    glow=False,
    glow_color=None,
):
    image = font(size, bold).render(text, True, color)
    rect = image.get_rect(**{anchor: position})
    if glow:
        gc = glow_color or color
        glow_surf = pygame.Surface(
            (image.get_width() + 20, image.get_height() + 20), pygame.SRCALPHA
        )
        glow_img = font(size, bold).render(text, True, (*gc[:3], 120) if len(gc) >= 3 else gc)
        for dx, dy in ((-2, 0), (2, 0), (0, -2), (0, 2), (-1, -1), (1, 1), (-1, 1), (1, -1)):
            glow_surf.blit(glow_img, (10 + dx, 10 + dy))
        surface.blit(glow_surf, (rect.x - 10, rect.y - 10))
    surface.blit(image, rect)
    return rect


def rounded_rect(
    surface,
    color,
    rect,
    radius=16,
    border=0,
    border_color=None,
):
    pygame.draw.rect(surface, color, rect, border_radius=radius)

    if border and border_color:
        pygame.draw.rect(
            surface,
            border_color,
            rect,
            border,
            border_radius=radius,
        )


def drop_shadow(surface, rect, radius=20, offset=6, alpha=90):
    shadow_rect = rect.move(0, offset)
    shadow_surf = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
    pygame.draw.rect(
        shadow_surf,
        (*SHADOW, alpha),
        shadow_rect,
        border_radius=radius,
    )
    surface.blit(shadow_surf, (0, 0))


def soft_glow(surface, center, radius, color, layers=4, max_alpha=70):
    glow = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
    for i in range(layers, 0, -1):
        alpha = int(max_alpha * (i / layers) * 0.4)
        r = int(radius * (1 + (layers - i) * 0.45))
        pygame.draw.circle(glow, (*color, alpha), center, r)
    surface.blit(glow, (0, 0))


def vertical_gradient(surface, rect, top_color, bottom_color):
    height = rect.height
    for y in range(height):
        t = y / max(1, height - 1)
        color = (
            int(top_color[0] + (bottom_color[0] - top_color[0]) * t),
            int(top_color[1] + (bottom_color[1] - top_color[1]) * t),
            int(top_color[2] + (bottom_color[2] - top_color[2]) * t),
        )
        pygame.draw.line(
            surface, color, (rect.left, rect.top + y), (rect.right, rect.top + y)
        )


def draw_background(surface):
    vertical_gradient(
        surface,
        pygame.Rect(0, 0, WIDTH, HEIGHT),
        BACKGROUND,
        BACKGROUND_2,
    )

    grid_alpha_surf = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    for x in range(0, WIDTH, 48):
        pygame.draw.line(grid_alpha_surf, (255, 255, 255, 8), (x, 0), (x, HEIGHT))
    for y in range(0, HEIGHT, 48):
        pygame.draw.line(grid_alpha_surf, (255, 255, 255, 8), (0, y), (WIDTH, y))
    surface.blit(grid_alpha_surf, (0, 0))

    glow_surf = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    pygame.draw.circle(glow_surf, (94, 234, 212, 26), (WIDTH - 40, -30), 220)
    pygame.draw.circle(glow_surf, (120, 110, 255, 22), (-70, HEIGHT + 50), 240)
    surface.blit(glow_surf, (0, 0))


def cell_center(cell):
    return (
        BOARD_RECT.left + cell[0] * CELL + CELL // 2,
        BOARD_RECT.top + cell[1] * CELL + CELL // 2,
    )


class SnakeGame:
    def __init__(self):
        self.high_score = load_high_score()
        self.fullscreen = True
        self.screen = pygame.display.set_mode(
            (WIDTH, HEIGHT),
            pygame.SCALED | pygame.FULLSCREEN,
        )
        self.clock = pygame.time.Clock()
        self.running = True
        self.state = "menu"
        self.menu_index = 0
        self.overlay_index = 0
        self.score = 0
        self.snake = []
        self.direction = (1, 0)
        self.next_direction = (1, 0)
        self.apple = (0, 0)
        self.move_timer = 0.0
        self.last_time = pygame.time.get_ticks()

        self.start_game()

    def start_game(self):
        center = (GRID_COLS // 2, GRID_ROWS // 2)

        self.snake = [
            center,
            (center[0] - 1, center[1]),
            (center[0] - 2, center[1]),
        ]

        self.direction = (1, 0)
        self.next_direction = (1, 0)
        self.score = 0
        self.move_timer = 0.0

        self.spawn_apple()

    def spawn_apple(self):
        free_cells = [
            (x, y)
            for x in range(GRID_COLS)
            for y in range(GRID_ROWS)
            if (x, y) not in self.snake
        ]

        if free_cells:
            self.apple = random.choice(free_cells)
        else:
            self.apple = self.snake[0]

    def set_direction(self, direction):
        opposite_move = (
            direction[0] + self.direction[0] == 0
            and direction[1] + self.direction[1] == 0
        )

        if not opposite_move:
            self.next_direction = direction

    def toggle_fullscreen(self):
        self.fullscreen = not self.fullscreen
        flags = pygame.SCALED

        if self.fullscreen:
            flags |= pygame.FULLSCREEN

        self.screen = pygame.display.set_mode((WIDTH, HEIGHT), flags)

    def update(self, dt):
        self.move_timer += dt
        speed = max(0.065, 0.13 - self.score * 0.0015)

        while self.move_timer >= speed:
            self.move_timer -= speed
            self.direction = self.next_direction

            head_x, head_y = self.snake[0]

            new_head = (
                head_x + self.direction[0],
                head_y + self.direction[1],
            )

            hit_wall = not (
                0 <= new_head[0] < GRID_COLS
                and 0 <= new_head[1] < GRID_ROWS
            )
            hit_self = new_head in self.snake[:-1]

            if hit_wall or hit_self:
                self.high_score = max(self.high_score, self.score)
                save_high_score(self.high_score)
                self.state = "game_over"
                return

            self.snake.insert(0, new_head)

            if new_head == self.apple:
                self.score += 1

                if self.score > self.high_score:
                    self.high_score = self.score
                    save_high_score(self.high_score)

                self.spawn_apple()
            else:
                self.snake.pop()

    def draw_header(self):
        draw_text(
            self.screen,
            "NEON",
            (48, 28),
            28,
            ACCENT,
            True,
            glow=True,
        )

        draw_text(
            self.screen,
            "SNAKE",
            (132, 28),
            28,
            TEXT,
            True,
            glow=True,
            glow_color=(180, 140, 255),
        )

        draw_text(
            self.screen,
            "CLASSIC ARCADE • MODERN EDITION",
            (48, 70),
            13,
            MUTED,
            True,
        )

        score_rect = pygame.Rect(702, 28, 98, 52)
        high_rect = pygame.Rect(814, 28, 98, 52)

        for rect in (score_rect, high_rect):
            drop_shadow(self.screen, rect, radius=14, offset=4, alpha=70)
            rounded_rect(self.screen, PANEL, rect, 14, 1, PANEL_LIGHT)

        draw_text(
            self.screen,
            "SCORE",
            score_rect.center,
            10,
            MUTED,
            True,
            "midtop",
        )

        draw_text(
            self.screen,
            str(self.score),
            score_rect.center,
            22,
            TEXT,
            True,
            "midbottom",
        )

        draw_text(
            self.screen,
            "BEST",
            high_rect.center,
            10,
            MUTED,
            True,
            "midtop",
        )

        draw_text(
            self.screen,
            str(self.high_score),
            high_rect.center,
            22,
            GOLD,
            True,
            "midbottom",
        )

    def draw_board(self):
        drop_shadow(self.screen, BOARD_RECT, radius=22, offset=8, alpha=100)
        rounded_rect(self.screen, PANEL, BOARD_RECT, 22, 1, PANEL_LIGHT)

        inner = BOARD_RECT.inflate(-6, -6)
        rounded_rect(self.screen, (12, 19, 34), inner, 18)

        grid_surf = pygame.Surface(self.screen.get_size(), pygame.SRCALPHA)
        for x in range(GRID_COLS + 1):
            px = BOARD_RECT.left + x * CELL
            pygame.draw.line(
                grid_surf, (255, 255, 255, 14), (px, inner.top), (px, inner.bottom)
            )
        for y in range(GRID_ROWS + 1):
            py = BOARD_RECT.top + y * CELL
            pygame.draw.line(
                grid_surf, (255, 255, 255, 14), (inner.left, py), (inner.right, py)
            )
        self.screen.blit(grid_surf, (0, 0))

        # --- 3D Apple -------------------------------------------------------
        apple_x, apple_y = cell_center(self.apple)
        t = pygame.time.get_ticks()
        pulse = 1 + math.sin(t * 0.005) * 0.06
        bob_y = math.sin(t * 0.004) * 1.5
        ax, ay = apple_x, apple_y + bob_y

        # outer glow
        soft_glow(self.screen, (int(ax), int(ay)), int(CELL * 1.2), APPLE_GLOW, layers=5, max_alpha=55)

        r = int(CELL * 0.38 * pulse)
        glow_s = pygame.Surface((r * 6, r * 6), pygame.SRCALPHA)
        gc = (r * 3, r * 3)
        # drop shadow
        pygame.draw.circle(glow_s, (60, 10, 30, 60), (gc[0], gc[1] + 4), r)
        # base sphere
        for i in range(r, 0, -1):
            ratio = i / r
            cr = int(180 + 75 * (1 - ratio))
            cg = int(20 + 70 * (1 - ratio) * (1 - ratio))
            cb = int(60 + 65 * (1 - ratio))
            pygame.draw.circle(glow_s, (cr, cg, cb, 255), (gc[0] - int(r * 0.08), gc[1] - int(r * 0.08)), i)
        # specular highlight
        spec_r = max(2, r // 3)
        spec_s = pygame.Surface((spec_r * 4, spec_r * 4), pygame.SRCALPHA)
        for si in range(spec_r, 0, -1):
            a = int(200 * (si / spec_r))
            pygame.draw.circle(spec_s, (255, 255, 255, a), (spec_r * 2, spec_r * 2), si)
        glow_s.blit(spec_s, (gc[0] - r // 2 - spec_r * 2, gc[1] - r // 2 - spec_r * 2))
        # bottom rim light
        rim_r = max(1, r // 4)
        for ri in range(rim_r, 0, -1):
            a = int(80 * (ri / rim_r))
            pygame.draw.circle(glow_s, (255, 180, 200, a), (gc[0] + r // 4, gc[1] + r // 3), ri)
        self.screen.blit(glow_s, (int(ax) - r * 3, int(ay) - r * 3))

        # stem
        pygame.draw.line(self.screen, (110, 75, 45), (int(ax), int(ay) - r + 1), (int(ax) + 2, int(ay) - r - 6), 2)
        # leaf
        leaf_pts = [
            (int(ax) + 2, int(ay) - r - 5),
            (int(ax) + 8, int(ay) - r - 9),
            (int(ax) + 6, int(ay) - r - 3),
        ]
        pygame.draw.polygon(self.screen, (80, 220, 100), leaf_pts)

        # sparkle
        sparkle_a = int(120 + 100 * math.sin(t * 0.008))
        sp_x = int(ax) - r // 3
        sp_y = int(ay) - r // 3
        sp_surf = pygame.Surface((6, 6), pygame.SRCALPHA)
        pygame.draw.circle(sp_surf, (255, 255, 255, sparkle_a), (3, 3), 2)
        self.screen.blit(sp_surf, (sp_x - 3, sp_y - 3))

        # --- 3D Snake -------------------------------------------------------
        head_x, head_y = cell_center(self.snake[0])
        soft_glow(self.screen, (head_x, head_y), int(CELL * 1.0), ACCENT_GLOW, layers=5, max_alpha=50)

        # draw connectors between adjacent segments first (behind spheres)
        for idx in range(len(self.snake) - 1):
            x1, y1 = cell_center(self.snake[idx])
            x2, y2 = cell_center(self.snake[idx + 1])
            connector_w = int(CELL * 0.42)
            pygame.draw.line(self.screen, (8, 100, 110), (x1, y1 + 2), (x2, y2 + 2), connector_w)  # shadow
            pygame.draw.line(self.screen, (30, 190, 170), (x1, y1), (x2, y2), connector_w)
            pygame.draw.line(self.screen, (80, 230, 210), (x1, y1 - 1), (x2, y2 - 1), max(2, connector_w // 3))

        for index, segment in enumerate(reversed(self.snake)):
            x, y = cell_center(segment)
            is_head = index == len(self.snake) - 1
            sphere_r = int(CELL * (0.44 if is_head else 0.38))

            # 3D sphere via concentric circles
            base_color = ACCENT if is_head else (39, 205, 181)
            dark_color = (max(0, base_color[0] - 50), max(0, base_color[1] - 50), max(0, base_color[2] - 50))
            light_color = (min(255, base_color[0] + 80), min(255, base_color[1] + 50), min(255, base_color[2] + 40))

            sphere_s = pygame.Surface((sphere_r * 4, sphere_r * 4), pygame.SRCALPHA)
            sc = (sphere_r * 2, sphere_r * 2)
            # drop shadow
            pygame.draw.circle(sphere_s, (5, 50, 60, 80), (sc[0], sc[1] + 3), sphere_r)
            # gradient sphere
            for si in range(sphere_r, 0, -1):
                ratio = si / sphere_r
                c = (
                    int(dark_color[0] + (base_color[0] - dark_color[0]) * (1 - ratio)),
                    int(dark_color[1] + (base_color[1] - dark_color[1]) * (1 - ratio)),
                    int(dark_color[2] + (base_color[2] - dark_color[2]) * (1 - ratio)),
                    255,
                )
                pygame.draw.circle(sphere_s, c, (sc[0] - int(sphere_r * 0.1), sc[1] - int(sphere_r * 0.1)), si)
            # top specular
            spec_sr = max(2, sphere_r // 3)
            for sri in range(spec_sr, 0, -1):
                a = int(180 * (sri / spec_sr))
                pygame.draw.circle(sphere_s, (min(255, light_color[0] + 60), min(255, light_color[1] + 60), 255, a),
                                   (sc[0] - sphere_r // 3, sc[1] - sphere_r // 3), sri)
            # bottom rim
            for bri in range(max(1, sphere_r // 5), 0, -1):
                a = int(60 * (bri / max(1, sphere_r // 5)))
                pygame.draw.circle(sphere_s, (*light_color, a),
                                   (sc[0] + sphere_r // 4, sc[1] + sphere_r // 4), bri)

            self.screen.blit(sphere_s, (x - sphere_r * 2, y - sphere_r * 2))

            if is_head:
                eo_x = int(3.5 * self.direction[0])
                eo_y = int(3.5 * self.direction[1])
                # eye whites
                pygame.draw.circle(self.screen, (220, 240, 240), (x - 4 + eo_x, y - 2 + eo_y), 4)
                pygame.draw.circle(self.screen, (220, 240, 240), (x + 4 + eo_x, y - 2 + eo_y), 4)
                # pupils
                pygame.draw.circle(self.screen, (5, 25, 30), (x - 4 + eo_x + self.direction[0], y - 2 + eo_y + self.direction[1]), 2)
                pygame.draw.circle(self.screen, (5, 25, 30), (x + 4 + eo_x + self.direction[0], y - 2 + eo_y + self.direction[1]), 2)
                # eye shine
                pygame.draw.circle(self.screen, (255, 255, 255), (x - 3 + eo_x, y - 3 + eo_y), 1)
                pygame.draw.circle(self.screen, (255, 255, 255), (x + 5 + eo_x, y - 3 + eo_y), 1)

    def draw_hamburger(self):
        button = pygame.Rect(850, 104, 62, 42)

        drop_shadow(self.screen, button, radius=12, offset=3, alpha=60)
        rounded_rect(self.screen, PANEL_LIGHT, button, 12, 1, (40, 54, 84))

        for offset in (-7, 0, 7):
            pygame.draw.line(
                self.screen,
                TEXT,
                (
                    button.centerx - 11,
                    button.centery + offset,
                ),
                (
                    button.centerx + 11,
                    button.centery + offset,
                ),
                2,
            )

        return button

    def draw_menu(self):
        draw_background(self.screen)

        draw_text(
            self.screen,
            "NEON",
            (WIDTH // 2, 100),
            64,
            ACCENT,
            True,
            "midtop",
            glow=True,
        )

        draw_text(
            self.screen,
            "SNAKE",
            (WIDTH // 2, 166),
            64,
            TEXT,
            True,
            "midtop",
            glow=True,
            glow_color=(180, 140, 255),
        )

        draw_text(
            self.screen,
            "A clean, modern take on the classic arcade game",
            (WIDTH // 2, 246),
            16,
            MUTED,
            anchor="midtop",
        )

        options = ["Play", "Highscore", "Exit"]

        for index, option in enumerate(options):
            rect = pygame.Rect(
                WIDTH // 2 - 170,
                306 + index * 64,
                340,
                48,
            )

            selected = index == self.menu_index

            drop_shadow(self.screen, rect, radius=14, offset=4, alpha=70)
            rounded_rect(
                self.screen,
                ACCENT_DARK if selected else PANEL,
                rect,
                14,
                1,
                ACCENT if selected else PANEL_LIGHT,
            )

            if selected:
                bar = pygame.Rect(rect.left, rect.top + 8, 4, rect.height - 16)
                rounded_rect(self.screen, ACCENT, bar, 2)

            draw_text(
                self.screen,
                f"{index + 1}.",
                (rect.left + 26, rect.centery),
                16,
                TEXT if selected else MUTED,
                True,
                "midleft",
            )

            draw_text(
                self.screen,
                option,
                (rect.left + 74, rect.centery),
                17,
                TEXT,
                True,
                "midleft",
            )

        draw_text(
            self.screen,
            "↑ ↓  Navigate     ENTER  Select     ESC  Quit",
            (WIDTH // 2, 550),
            13,
            MUTED,
            anchor="midtop",
        )

    def draw_overlay(self, title, subtitle, options):
        shade = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        shade.fill((3, 7, 15, 195))
        self.screen.blit(shade, (0, 0))

        card = pygame.Rect(
            WIDTH // 2 - 190,
            172,
            380,
            280,
        )

        drop_shadow(self.screen, card, radius=22, offset=8, alpha=120)
        rounded_rect(
            self.screen,
            PANEL,
            card,
            22,
            1,
            PANEL_LIGHT,
        )

        draw_text(
            self.screen,
            title,
            (WIDTH // 2, 204),
            32,
            TEXT,
            True,
            "midtop",
            glow=True,
            glow_color=ACCENT,
        )

        draw_text(
            self.screen,
            subtitle,
            (WIDTH // 2, 250),
            14,
            MUTED,
            anchor="midtop",
        )

        for index, option in enumerate(options):
            rect = pygame.Rect(
                card.left + 34,
                286 + index * 54,
                card.width - 68,
                42,
            )

            selected = index == self.overlay_index

            rounded_rect(
                self.screen,
                ACCENT_DARK if selected else PANEL_LIGHT,
                rect,
                12,
                1,
                ACCENT if selected else (40, 54, 84),
            )

            draw_text(
                self.screen,
                f"{index + 1}.  {option}",
                rect.center,
                15,
                TEXT,
                True,
                "center",
            )

        draw_text(
            self.screen,
            "↑ ↓  Navigate     ENTER  Select",
            (WIDTH // 2, 420),
            12,
            MUTED,
            anchor="midtop",
        )

    def draw_play(self):
        draw_background(self.screen)
        self.draw_header()
        self.draw_board()
        self.draw_hamburger()

        draw_text(
            self.screen,
            "ARROWS / WASD TO MOVE   •   WALLS END THE RUN   •   P / ESC PAUSE",
            (48, 604),
            12,
            MUTED,
            True,
        )

        if self.state == "paused":
            self.draw_overlay(
                "Paused",
                "Take a breath. Your run is waiting.",
                ["Resume", "Retry", "Exit"],
            )

        elif self.state == "game_over":
            self.draw_overlay(
                "GAME OVER",
                f"Final score: {self.score}  •  Watch the walls",
                ["Retry", "Exit"],
            )

    def draw(self):
        if self.state == "menu":
            self.draw_menu()

        elif self.state == "highscore":
            draw_background(self.screen)

            draw_text(
                self.screen,
                "HIGH SCORE",
                (WIDTH // 2, 125),
                46,
                TEXT,
                True,
                "midtop",
                glow=True,
                glow_color=GOLD,
            )

            draw_text(
                self.screen,
                "Your best run",
                (WIDTH // 2, 190),
                16,
                MUTED,
                anchor="midtop",
            )

            card = pygame.Rect(
                WIDTH // 2 - 150,
                254,
                300,
                130,
            )
            drop_shadow(self.screen, card, radius=24, offset=6, alpha=90)
            rounded_rect(self.screen, PANEL, card, 24, 1, PANEL_LIGHT)

            draw_text(
                self.screen,
                str(self.high_score),
                (WIDTH // 2, 282),
                66,
                GOLD,
                True,
                "midtop",
                glow=True,
                glow_color=GOLD,
            )

            draw_text(
                self.screen,
                "POINTS",
                (WIDTH // 2, 355),
                13,
                MUTED,
                True,
                "midtop",
            )

            draw_text(
                self.screen,
                "ENTER / ESC  Back to menu",
                (WIDTH // 2, 520),
                13,
                MUTED,
                anchor="midtop",
            )

        else:
            self.draw_play()

        pygame.display.flip()

    def choose_menu(self):
        if self.menu_index == 0:
            self.start_game()
            self.state = "playing"

        elif self.menu_index == 1:
            self.state = "highscore"

        else:
            self.running = False

    def choose_overlay(self):
        if self.state == "paused":
            if self.overlay_index == 0:
                self.state = "playing"

            elif self.overlay_index == 1:
                self.start_game()
                self.state = "playing"

            else:
                self.state = "menu"

        elif self.state == "game_over":
            if self.overlay_index == 0:
                self.start_game()
                self.state = "playing"

            else:
                self.state = "menu"

    def handle_event(self, event):
        if event.type == pygame.QUIT:
            self.running = False

        if event.type != pygame.KEYDOWN:
            return

        if event.key == pygame.K_F11:
            self.toggle_fullscreen()
            return

        if self.state == "menu":
            if event.key in (pygame.K_UP, pygame.K_w):
                self.menu_index = (self.menu_index - 1) % 3

            elif event.key in (pygame.K_DOWN, pygame.K_s):
                self.menu_index = (self.menu_index + 1) % 3

            elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                self.choose_menu()

            elif event.key == pygame.K_ESCAPE:
                self.running = False

        elif self.state == "highscore":
            if event.key in (pygame.K_RETURN, pygame.K_ESCAPE):
                self.state = "menu"

        elif self.state == "playing":
            directions = {
                pygame.K_UP: (0, -1),
                pygame.K_w: (0, -1),
                pygame.K_DOWN: (0, 1),
                pygame.K_s: (0, 1),
                pygame.K_LEFT: (-1, 0),
                pygame.K_a: (-1, 0),
                pygame.K_RIGHT: (1, 0),
                pygame.K_d: (1, 0),
            }

            if event.key in directions:
                self.set_direction(directions[event.key])

            elif event.key in (pygame.K_ESCAPE, pygame.K_p):
                self.overlay_index = 0
                self.state = "paused"

        elif self.state in ("paused", "game_over"):
            options_count = 3 if self.state == "paused" else 2

            if event.key in (pygame.K_UP, pygame.K_w):
                self.overlay_index = (
                    self.overlay_index - 1
                ) % options_count

            elif event.key in (pygame.K_DOWN, pygame.K_s):
                self.overlay_index = (
                    self.overlay_index + 1
                ) % options_count

            elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                self.choose_overlay()

            elif event.key == pygame.K_ESCAPE:
                self.state = "menu"

    def run(self):
        while self.running:
            now = pygame.time.get_ticks()

            dt = min(
                (now - self.last_time) / 1000.0,
                0.1,
            )

            self.last_time = now

            for event in pygame.event.get():
                self.handle_event(event)

            if self.state == "playing":
                self.update(dt)

            self.draw()
            self.clock.tick(FPS)

        pygame.quit()


if __name__ == "__main__":
    SnakeGame().run()