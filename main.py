"""
MAZE QUEST — Treasure Hunt & Pathfinding Visualizer
===================================================

A polished pygame game that combines:
  * A playable treasure-hunt maze (move a hero, collect gems, reach the goal)
  * Live visualization of BFS / DFS / A* pathfinding
  * A clean, button-driven control panel with stats, legend and speed control

Controls
--------
  Arrow keys .... move the hero
  1 / 2 / 3 ..... select BFS / DFS / A*
  SPACE ......... run the solver (animated search + path reveal)
  ENTER ......... step the hero one cell along the found path
  P ............. auto-walk the hero along the found path
  G ............. generate a new maze
  R ............. reset hero + treasures
  C ............. clear the search overlay
  B ............. empty the grid (build your own walls)
  - / = ......... visualization speed down / up
  ESC ........... quit

  Left click .......... toggle a wall
  Shift + left click .. move the GOAL
  Right click ......... move the START

Requires: pygame 2.x   ->   pip install pygame
Run:      python maze_quest.py
"""

import sys
import math
import time
import random
from collections import deque
from heapq import heappush, heappop
from itertools import count

import pygame

# --------------------------------------------------------------------------- #
#  Configuration
# --------------------------------------------------------------------------- #
CELL = 26
COLS = 29          # odd numbers give clean mazes
ROWS = 21
SIDEBAR_W = 280
STATUS_H = 56

MAZE_W = COLS * CELL
MAZE_H = ROWS * CELL
WIDTH = MAZE_W + SIDEBAR_W
HEIGHT = MAZE_H + STATUS_H
FPS = 60

N_TREASURES = 6
SPEED_LEVELS = [8, 15, 30, 60, 120, 240]   # search steps per second
WALK_SPEED = 12                            # hero cells per second when auto-walking

# --------------------------------------------------------------------------- #
#  Palette
# --------------------------------------------------------------------------- #
COL = {
    "bg":         (15, 18, 26),
    "panel":      (22, 27, 36),
    "panel2":     (30, 36, 48),
    "border":     (44, 52, 68),
    "floor":      (240, 243, 249),
    "floor2":     (231, 235, 243),
    "grid":       (218, 223, 233),
    "wall":       (33, 40, 56),
    "wall_edge":  (52, 62, 84),
    "start":      (46, 204, 113),
    "start_dk":   (33, 158, 88),
    "goal":       (241, 196, 15),
    "goal_dk":    (176, 137, 12),
    "frontier":   (120, 190, 236),
    "visited":    (176, 187, 226),
    "path":       (155, 89, 182),
    "player":     (231, 111, 81),
    "player_dk":  (170, 70, 45),
    "treasure":   (243, 176, 32),
    "treasure_dk":(190, 130, 12),
    "text":       (233, 237, 243),
    "text_dim":   (150, 160, 176),
    "accent":     (95, 175, 240),
    "good":       (46, 204, 113),
    "bad":        (231, 76, 60),
    "btn":        (37, 44, 60),
    "btn_hover":  (52, 62, 84),
    "btn_active": (52, 120, 200),
}


# --------------------------------------------------------------------------- #
#  Small drawing helpers
# --------------------------------------------------------------------------- #
def star_points(cx, cy, outer, inner, n=5, rot=-90):
    pts = []
    for i in range(n * 2):
        ang = math.radians(rot + i * 180.0 / n)
        rad = outer if i % 2 == 0 else inner
        pts.append((cx + rad * math.cos(ang), cy + rad * math.sin(ang)))
    return pts


def diamond_points(cx, cy, w, h):
    return [(cx, cy - h), (cx + w, cy), (cx, cy + h), (cx - w, cy)]


# --------------------------------------------------------------------------- #
#  Grid / maze model
# --------------------------------------------------------------------------- #
class Grid:
    def __init__(self):
        self.rows = ROWS
        self.cols = COLS
        self.walls = [[False] * COLS for _ in range(ROWS)]
        self.start = (1, 1)
        self.goal = (ROWS - 2, COLS - 2)
        self.treasures = set()

    def in_bounds(self, r, c):
        return 0 <= r < self.rows and 0 <= c < self.cols

    def is_wall(self, r, c):
        return self.walls[r][c]

    def neighbors(self, r, c):
        for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            nr, nc = r + dr, c + dc
            if self.in_bounds(nr, nc) and not self.walls[nr][nc]:
                yield (nr, nc)

    def clear_walls(self):
        for i in range(self.rows):
            for j in range(self.cols):
                self.walls[i][j] = False

    def generate(self):
        """Iterative recursive-backtracker (no recursion-limit issues)."""
        for i in range(self.rows):
            for j in range(self.cols):
                self.walls[i][j] = True

        start = (1, 1)
        self.walls[1][1] = False
        stack = [start]
        visited = {start}
        while stack:
            r, c = stack[-1]
            options = []
            for dr, dc in ((-2, 0), (2, 0), (0, -2), (0, 2)):
                nr, nc = r + dr, c + dc
                if 1 <= nr < self.rows - 1 and 1 <= nc < self.cols - 1 and (nr, nc) not in visited:
                    options.append((nr, nc, dr, dc))
            if options:
                nr, nc, dr, dc = random.choice(options)
                self.walls[r + dr // 2][c + dc // 2] = False
                self.walls[nr][nc] = False
                visited.add((nr, nc))
                stack.append((nr, nc))
            else:
                stack.pop()

        self.start = (1, 1)
        self.goal = (self.rows - 2, self.cols - 2)
        self.walls[self.start[0]][self.start[1]] = False
        self.walls[self.goal[0]][self.goal[1]] = False

    def place_treasures(self, n):
        floors = [
            (r, c)
            for r in range(self.rows)
            for c in range(self.cols)
            if not self.walls[r][c] and (r, c) not in (self.start, self.goal)
        ]
        random.shuffle(floors)
        self.treasures = set(floors[:min(n, len(floors))])


# --------------------------------------------------------------------------- #
#  Clickable button
# --------------------------------------------------------------------------- #
class Button:
    def __init__(self, rect, label, cb, active_fn=None):
        self.rect = pygame.Rect(rect)
        self.label = label
        self.cb = cb
        self.active_fn = active_fn
        self.hover = False

    def draw(self, game):
        active = bool(self.active_fn and self.active_fn())
        if active:
            base = COL["btn_active"]
        elif self.hover:
            base = COL["btn_hover"]
        else:
            base = COL["btn"]
        pygame.draw.rect(game.screen, base, self.rect, border_radius=8)
        pygame.draw.rect(game.screen, COL["border"], self.rect, 1, border_radius=8)
        col = (255, 255, 255) if active else COL["text"]
        txt = game.font_btn.render(self.label, True, col)
        game.screen.blit(txt, txt.get_rect(center=self.rect.center))

    def click(self, pos):
        if self.rect.collidepoint(pos):
            self.cb()
            return True
        return False


# --------------------------------------------------------------------------- #
#  Game
# --------------------------------------------------------------------------- #
class Game:
    def __init__(self):
        pygame.init()
        pygame.key.set_repeat(200, 90)
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        pygame.display.set_caption("Maze Quest — Treasure Hunt & Pathfinding")
        self.clock = pygame.time.Clock()

        self.font_title = self._font(26, bold=True)
        self.font_h = self._font(14, bold=True)
        self.font_btn = self._font(15)
        self.font = self._font(15)
        self.font_sm = self._font(13)
        self.font_status = self._font(16)

        self.grid = Grid()
        self.algorithm = "A*"
        self.speed_idx = 3

        # runtime / animation state
        self.player = self.grid.start
        self.collected = set()
        self.moves = 0
        self.won = False
        self.play_start = time.time()
        self.win_time = None

        self.visited = set()
        self.frontier = set()
        self.path = []
        self.path_i = 1
        self.nodes = 0
        self.state = "idle"          # idle | searching | walking
        self.search_gen = None
        self.search_acc = 0.0
        self.walk_acc = 0.0

        self.message = "Welcome to Maze Quest!  Press G for a new maze."
        self.msg_color = COL["accent"]

        self.buttons = []
        self._build_buttons()
        self.new_maze()

    # ---- fonts ----------------------------------------------------------- #
    def _font(self, size, bold=False):
        for name in ("Segoe UI", "Helvetica Neue", "Arial", "DejaVu Sans"):
            try:
                f = pygame.font.SysFont(name, size, bold=bold)
                if f:
                    return f
            except Exception:
                pass
        return pygame.font.Font(None, size + 4)

    @property
    def speed(self):
        return SPEED_LEVELS[self.speed_idx]

    @property
    def score(self):
        s = len(self.collected) * 100
        if self.won:
            s += 500
            if self.grid.treasures and len(self.collected) == len(self.grid.treasures):
                s += 300
        return s

    # ---- lifecycle ------------------------------------------------------- #
    def new_maze(self):
        self.grid.generate()
        self.grid.place_treasures(N_TREASURES)
        self._fresh_run()
        self.set_message("New maze generated — collect the gems and reach the star!", COL["accent"])

    def reset_run(self):
        self._fresh_run()
        self.set_message("Reset — hero back to start, treasures restored.", COL["accent"])

    def _fresh_run(self):
        self.player = self.grid.start
        self.collected = set()
        self.moves = 0
        self.won = False
        self.win_time = None
        self.play_start = time.time()
        self.clear_search()

    def empty_grid(self):
        self.grid.clear_walls()
        self.grid.treasures = set()
        self._fresh_run()
        self.set_message("Grid cleared — left-click to draw walls.", COL["accent"])

    def clear_search(self):
        self.visited = set()
        self.frontier = set()
        self.path = []
        self.path_i = 1
        self.nodes = 0
        self.state = "idle"
        self.search_gen = None

    def set_message(self, text, color=None):
        self.message = text
        self.msg_color = color or COL["text"]

    def set_algorithm(self, algo):
        self.algorithm = algo
        self.set_message(f"Algorithm set to {algo}.", COL["accent"])

    def change_speed(self, delta):
        self.speed_idx = max(0, min(len(SPEED_LEVELS) - 1, self.speed_idx + delta))

    # ---- solving --------------------------------------------------------- #
    def start_solve(self):
        if self.player == self.grid.goal:
            self.set_message("Hero is already on the goal.", COL["good"])
            return
        self.clear_search()
        self.state = "searching"
        self.search_acc = 0.0
        gens = {"BFS": self._gen_bfs, "DFS": self._gen_dfs, "A*": self._gen_astar}
        self.search_gen = gens[self.algorithm]()
        self.set_message(f"Running {self.algorithm}…", COL["accent"])

    def _build_path(self, came):
        goal = self.grid.goal
        if goal not in came:
            self.path = []
            return
        cur, path = goal, []
        while cur is not None:
            path.append(cur)
            cur = came.get(cur)
        path.reverse()
        self.path = path
        self.path_i = 1

    def _gen_bfs(self):
        g = self.grid
        start, goal = self.player, g.goal
        q = deque([start])
        came = {start: None}
        seen = {start}
        while q:
            cur = q.popleft()
            self.frontier.discard(cur)
            if cur != start:
                self.visited.add(cur)
            self.nodes += 1
            if cur == goal:
                self._build_path(came)
                return
            for nb in g.neighbors(*cur):
                if nb not in seen:
                    seen.add(nb)
                    came[nb] = cur
                    q.append(nb)
                    self.frontier.add(nb)
            yield
        self.path = []

    def _gen_dfs(self):
        g = self.grid
        start, goal = self.player, g.goal
        stack = [start]
        came = {start: None}
        seen = {start}
        while stack:
            cur = stack.pop()
            self.frontier.discard(cur)
            if cur != start:
                self.visited.add(cur)
            self.nodes += 1
            if cur == goal:
                self._build_path(came)
                return
            for nb in g.neighbors(*cur):
                if nb not in seen:
                    seen.add(nb)
                    came[nb] = cur
                    stack.append(nb)
                    self.frontier.add(nb)
            yield
        self.path = []

    def _gen_astar(self):
        g = self.grid
        start, goal = self.player, g.goal
        h = lambda a: abs(a[0] - goal[0]) + abs(a[1] - goal[1])
        gscore = {start: 0}
        came = {start: None}
        tie = count()
        pq = [(h(start), 0, next(tie), start)]
        open_set = {start}
        while pq:
            _, gc, _, cur = heappop(pq)
            if cur not in open_set:
                continue
            open_set.discard(cur)
            self.frontier.discard(cur)
            if cur != start:
                self.visited.add(cur)
            self.nodes += 1
            if cur == goal:
                self._build_path(came)
                return
            for nb in g.neighbors(*cur):
                t = gc + 1
                if t < gscore.get(nb, 1e9):
                    gscore[nb] = t
                    came[nb] = cur
                    heappush(pq, (t + h(nb), t, next(tie), nb))
                    open_set.add(nb)
                    self.frontier.add(nb)
            yield
        self.path = []

    def _on_search_done(self):
        self.state = "idle"
        self.search_gen = None
        if self.path:
            self.set_message(
                f"{self.algorithm}: path found ({len(self.path) - 1} steps, {self.nodes} explored). "
                f"Press P to auto-walk.",
                COL["good"],
            )
        else:
            self.set_message("No path found — the goal is walled off.", COL["bad"])

    # ---- hero movement --------------------------------------------------- #
    def try_move(self, dr, dc):
        if self.state == "searching" or self.won:
            return
        # a manual move invalidates the current solved path
        if self.path:
            self.path = []
            self.path_i = 1
        r, c = self.player
        nr, nc = r + dr, c + dc
        if self.grid.in_bounds(nr, nc) and not self.grid.walls[nr][nc]:
            self.state = "idle"
            self._enter_cell((nr, nc))

    def _enter_cell(self, cell):
        self.player = cell
        self.moves += 1
        if cell in self.grid.treasures and cell not in self.collected:
            self.collected.add(cell)
            self.set_message(
                f"Gem collected!  ({len(self.collected)}/{len(self.grid.treasures)})",
                COL["treasure"],
            )
        if cell == self.grid.goal:
            self._win()

    def _win(self):
        self.won = True
        self.win_time = time.time()
        self.state = "idle"
        got, total = len(self.collected), len(self.grid.treasures)
        if total and got == total:
            self.set_message(f"PERFECT!  All {total} gems + goal.  Score {self.score}!", COL["good"])
        else:
            self.set_message(f"Goal reached!  Gems {got}/{total}.  Score {self.score}.", COL["good"])

    def step_path(self):
        if not self.path:
            self.set_message("No path yet — press SPACE to solve first.", COL["bad"])
            return
        if self.won:
            return
        if self.path_i < len(self.path):
            self._enter_cell(self.path[self.path_i])
            self.path_i += 1

    def auto_walk(self):
        if not self.path:
            self.set_message("No path yet — press SPACE to solve first.", COL["bad"])
            return
        if self.won:
            return
        self.state = "walking"
        self.walk_acc = 0.0

    # ---- per-frame update ------------------------------------------------ #
    def update(self, dt):
        if self.state == "searching" and self.search_gen:
            self.search_acc += dt
            interval = 1.0 / self.speed
            budget = 0
            while self.search_acc >= interval and budget < 600:
                self.search_acc -= interval
                budget += 1
                try:
                    next(self.search_gen)
                except StopIteration:
                    self._on_search_done()
                    break

        elif self.state == "walking":
            self.walk_acc += dt
            interval = 1.0 / WALK_SPEED
            while self.walk_acc >= interval and self.state == "walking":
                self.walk_acc -= interval
                if self.path_i < len(self.path) and not self.won:
                    self._enter_cell(self.path[self.path_i])
                    self.path_i += 1
                else:
                    self.state = "idle"

    # ---- event handling -------------------------------------------------- #
    def handle_key(self, key, mods):
        if key == pygame.K_ESCAPE:
            return False
        elif key == pygame.K_UP:
            self.try_move(-1, 0)
        elif key == pygame.K_DOWN:
            self.try_move(1, 0)
        elif key == pygame.K_LEFT:
            self.try_move(0, -1)
        elif key == pygame.K_RIGHT:
            self.try_move(0, 1)
        elif key == pygame.K_1:
            self.set_algorithm("BFS")
        elif key == pygame.K_2:
            self.set_algorithm("DFS")
        elif key == pygame.K_3:
            self.set_algorithm("A*")
        elif key == pygame.K_SPACE:
            self.start_solve()
        elif key == pygame.K_RETURN:
            self.step_path()
        elif key == pygame.K_p:
            self.auto_walk()
        elif key == pygame.K_g:
            self.new_maze()
        elif key == pygame.K_r:
            self.reset_run()
        elif key == pygame.K_c:
            self.clear_search()
            self.set_message("Search overlay cleared.", COL["accent"])
        elif key == pygame.K_b:
            self.empty_grid()
        elif key in (pygame.K_MINUS, pygame.K_KP_MINUS):
            self.change_speed(-1)
        elif key in (pygame.K_EQUALS, pygame.K_PLUS, pygame.K_KP_PLUS):
            self.change_speed(1)
        return True

    def handle_click(self, pos, button, mods):
        mx, my = pos
        # sidebar buttons
        if mx >= MAZE_W:
            for b in self.buttons:
                if b.click(pos):
                    return
            return
        # maze editing (blocked mid-search)
        if my >= MAZE_H or self.state == "searching":
            return
        c, r = mx // CELL, my // CELL
        if not self.grid.in_bounds(r, c):
            return
        cell = (r, c)
        if button == 1:
            if mods & pygame.KMOD_SHIFT:
                if cell != self.grid.start and cell not in self.grid.treasures:
                    self.grid.goal = cell
                    self.grid.walls[r][c] = False
                    self.clear_search()
            elif cell not in (self.grid.start, self.grid.goal) and cell != self.player:
                self.grid.walls[r][c] = not self.grid.walls[r][c]
                self.grid.treasures.discard(cell)
                self.clear_search()
        elif button == 3:
            if cell != self.grid.goal and cell not in self.grid.treasures:
                self.grid.start = cell
                self.grid.walls[r][c] = False
                self.player = cell
                self.collected = set()
                self.moves = 0
                self.won = False
                self.clear_search()

    # ---- buttons layout -------------------------------------------------- #
    def _build_buttons(self):
        pad = 16
        x0 = MAZE_W + pad
        w = SIDEBAR_W - 2 * pad
        gap = 8
        # algorithm row (3)
        aw = (w - 2 * gap) // 3
        ay = 92
        for i, algo in enumerate(("BFS", "DFS", "A*")):
            self.buttons.append(
                Button((x0 + i * (aw + gap), ay, aw, 30), algo,
                       (lambda a=algo: self.set_algorithm(a)),
                       active_fn=(lambda a=algo: self.algorithm == a))
            )
        # action rows (2 cols)
        bw = (w - gap) // 2
        rows = [
            ("Generate", self.new_maze, "Solve", self.start_solve),
            ("Auto-Walk", self.auto_walk, "Clear", lambda: (self.clear_search(),
                                                            self.set_message("Search overlay cleared.",
                                                                             COL["accent"]))),
            ("Reset", self.reset_run, "Empty", self.empty_grid),
        ]
        by = 138
        for l1, cb1, l2, cb2 in rows:
            self.buttons.append(Button((x0, by, bw, 30), l1, cb1))
            self.buttons.append(Button((x0 + bw + gap, by, bw, 30), l2, cb2))
            by += 38
        # speed -/+ buttons
        sy = 268
        self.buttons.append(Button((x0 + w - 64, sy, 28, 26), "–", lambda: self.change_speed(-1)))
        self.buttons.append(Button((x0 + w - 30, sy, 28, 26), "+", lambda: self.change_speed(1)))

    # ---- rendering ------------------------------------------------------- #
    def render(self):
        self.screen.fill(COL["bg"])
        self._draw_maze()
        self._draw_sidebar()
        self._draw_status()
        pygame.display.flip()

    def _cell_rect(self, r, c):
        return pygame.Rect(c * CELL, r * CELL, CELL, CELL)

    def _draw_maze(self):
        g = self.grid
        # floor + walls
        for r in range(g.rows):
            for c in range(g.cols):
                rect = self._cell_rect(r, c)
                if g.walls[r][c]:
                    pygame.draw.rect(self.screen, COL["wall"], rect)
                    pygame.draw.line(self.screen, COL["wall_edge"], rect.topleft, rect.topright)
                    pygame.draw.line(self.screen, COL["wall_edge"], rect.topleft, rect.bottomleft)
                else:
                    shade = COL["floor"] if (r + c) % 2 == 0 else COL["floor2"]
                    pygame.draw.rect(self.screen, shade, rect)
                    pygame.draw.rect(self.screen, COL["grid"], rect, 1)

        special = {g.start, g.goal}

        def overlay(cell, color):
            r, c = cell
            if cell in special or g.walls[r][c]:
                return
            rr = self._cell_rect(r, c).inflate(-6, -6)
            pygame.draw.rect(self.screen, color, rr, border_radius=6)

        for cell in self.visited:
            overlay(cell, COL["visited"])
        for cell in self.frontier:
            overlay(cell, COL["frontier"])
        for cell in self.path:
            overlay(cell, COL["path"])

        # treasures
        for (r, c) in g.treasures:
            if (r, c) in self.collected:
                continue
            rect = self._cell_rect(r, c)
            cx, cy = rect.center
            pts = diamond_points(cx, cy, CELL * 0.24, CELL * 0.30)
            pygame.draw.polygon(self.screen, COL["treasure"], pts)
            pygame.draw.polygon(self.screen, COL["treasure_dk"], pts, 2)
            pygame.draw.line(self.screen, (255, 255, 255),
                             (cx - 3, cy - 4), (cx - 5, cy), 2)

        # start pad
        sr = self._cell_rect(*g.start).inflate(-4, -4)
        pygame.draw.rect(self.screen, COL["start"], sr, border_radius=6)
        pygame.draw.circle(self.screen, (255, 255, 255), sr.center, CELL * 0.16, 2)

        # goal pad + star
        gr = self._cell_rect(*g.goal).inflate(-4, -4)
        pygame.draw.rect(self.screen, COL["goal"], gr, border_radius=6)
        gx, gy = gr.center
        pygame.draw.polygon(self.screen, COL["goal_dk"],
                            star_points(gx, gy, CELL * 0.30, CELL * 0.13))

        # hero
        if not (self.won and self.player == g.goal):
            pass
        hr = self._cell_rect(*self.player)
        hx, hy = hr.center
        rad = int(CELL * 0.34)
        pygame.draw.circle(self.screen, COL["player_dk"], (hx, hy + 1), rad + 1)
        pygame.draw.circle(self.screen, COL["player"], (hx, hy), rad)
        pygame.draw.circle(self.screen, (255, 255, 255), (hx - rad // 3, hy - rad // 3),
                           max(2, rad // 4))

    def _draw_sidebar(self):
        x = MAZE_W
        panel = pygame.Rect(x, 0, SIDEBAR_W, MAZE_H)
        pygame.draw.rect(self.screen, COL["panel"], panel)
        pygame.draw.line(self.screen, COL["border"], (x, 0), (x, MAZE_H), 2)
        pad = 16
        left = x + pad
        w = SIDEBAR_W - 2 * pad

        title = self.font_title.render("MAZE QUEST", True, COL["text"])
        self.screen.blit(title, (left, 14))
        sub = self.font_sm.render("Treasure Hunt · Pathfinding", True, COL["text_dim"])
        self.screen.blit(sub, (left, 46))

        self.screen.blit(self.font_h.render("ALGORITHM", True, COL["text_dim"]), (left, 72))

        for b in self.buttons:
            b.draw(self)

        # speed label + value
        sy = 268
        self.screen.blit(self.font_h.render("SPEED", True, COL["text_dim"]), (left, sy + 5))
        val = self.font.render(f"{self.speed}/s", True, COL["accent"])
        self.screen.blit(val, (left + w - 130, sy + 4))

        # stats box
        box = pygame.Rect(left, 306, w, 132)
        pygame.draw.rect(self.screen, COL["panel2"], box, border_radius=10)
        pygame.draw.rect(self.screen, COL["border"], box, 1, border_radius=10)
        elapsed = (self.win_time or time.time()) - self.play_start
        stats = [
            ("Score", str(self.score)),
            ("Time", self._fmt_time(elapsed)),
            ("Moves", str(self.moves)),
            ("Gems", f"{len(self.collected)}/{len(self.grid.treasures)}"),
            ("Explored", str(self.nodes)),
            ("Path len", str(max(0, len(self.path) - 1) if self.path else 0)),
        ]
        sy = box.y + 12
        for k, v in stats:
            self.screen.blit(self.font_sm.render(k, True, COL["text_dim"]), (box.x + 12, sy))
            vt = self.font_sm.render(v, True, COL["text"])
            self.screen.blit(vt, (box.right - 12 - vt.get_width(), sy))
            sy += 19

        # legend
        self.screen.blit(self.font_h.render("LEGEND", True, COL["text_dim"]), (left, 448))
        legend = [
            (COL["start"], "Start"), (COL["goal"], "Goal"),
            (COL["treasure"], "Gem"), (COL["player"], "Hero"),
            (COL["frontier"], "Frontier"), (COL["visited"], "Visited"),
            (COL["path"], "Path"), (COL["wall"], "Wall"),
        ]
        ly = 470
        col_w = w // 2
        for i, (color, name) in enumerate(legend):
            cx = left + (i % 2) * col_w
            cy = ly + (i // 2) * 20
            pygame.draw.rect(self.screen, color, (cx, cy + 2, 14, 14), border_radius=3)
            self.screen.blit(self.font_sm.render(name, True, COL["text"]), (cx + 20, cy))

    def _draw_status(self):
        bar = pygame.Rect(0, MAZE_H, WIDTH, STATUS_H)
        pygame.draw.rect(self.screen, COL["panel"], bar)
        pygame.draw.line(self.screen, COL["border"], (0, MAZE_H), (WIDTH, MAZE_H), 2)
        msg = self.font_status.render(self.message, True, self.msg_color)
        self.screen.blit(msg, (16, MAZE_H + 8))
        hint = "Arrows move · SPACE solve · ENTER step · P walk · G maze · R reset · B build · -/+ speed"
        ht = self.font_sm.render(hint, True, COL["text_dim"])
        self.screen.blit(ht, (16, MAZE_H + 32))

    @staticmethod
    def _fmt_time(t):
        t = max(0, int(t))
        return f"{t // 60:02d}:{t % 60:02d}"

    # ---- main loop ------------------------------------------------------- #
    def run(self):
        running = True
        while running:
            dt = self.clock.tick(FPS) / 1000.0
            mouse = pygame.mouse.get_pos()
            for b in self.buttons:
                b.hover = b.rect.collidepoint(mouse)

            for e in pygame.event.get():
                if e.type == pygame.QUIT:
                    running = False
                elif e.type == pygame.KEYDOWN:
                    if not self.handle_key(e.key, pygame.key.get_mods()):
                        running = False
                elif e.type == pygame.MOUSEBUTTONDOWN and e.button in (1, 3):
                    self.handle_click(e.pos, e.button, pygame.key.get_mods())

            self.update(dt)
            self.render()

        pygame.quit()
        sys.exit()


if __name__ == "__main__":
    Game().run()
