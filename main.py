import pygame
import sys
import random
from heapq import heappush, heappop
from collections import deque

CELL = 28
ROWS = 21
COLS = 31
WIDTH = CELL * COLS
HEIGHT = CELL * ROWS + 50

WHITE = (245, 245, 245)
BLACK = (20, 20, 20)
BLUE = (80,120,245)
GREEN = (60,200,100)
RED = (230,70,70)
PURPLE = (160,60,200)
GRAY = (170,170,170)
YELLOW = (250,220,80)
ORANGE = (255,165,0)

EMPTY=0; WALL=1; START=2; GOAL=3; OPEN=4; CLOSED=5; PATH=6; PLAYER=7

class Grid:
    def _init_(self,r,c):
        self.r=r;self.c=c
        self.g=[[EMPTY for _ in range(c)]for _ in range(r)]
        self.start=(1,1)
        self.goal=(r-2,c-2)
        self.player=self.start
        self.g[self.start[0]][self.start[1]]=START
        self.g[self.goal[0]][self.goal[1]]=GOAL

    def reset(self):
        for i in range(self.r):
            for j in range(self.c):
                if self.g[i][j]!=WALL:
                    self.g[i][j]=EMPTY
        self.g[self.start[0]][self.start[1]]=START
        self.g[self.goal[0]][self.goal[1]]=GOAL

    def neighbors(self,r,c):
        for dr,dc in [(-1,0),(1,0),(0,-1),(0,1)]:
            nr, nc = r+dr, c+dc
            if 0<=nr<self.r and 0<=nc<self.c and self.g[nr][nc]!=WALL:
                yield nr,nc


def generate_maze(G):
    for i in range(G.r):
        for j in range(G.c):
            G.g[i][j]=WALL

    def carve(r,c):
        G.g[r][c]=EMPTY
        dirs=[(2,0),(-2,0),(0,2),(0,-2)]
        random.shuffle(dirs)
        for dr,dc in dirs:
            nr,nc=r+dr,c+dc
            if 1<=nr<G.r-1 and 1<=nc<G.c-1 and G.g[nr][nc]==WALL:
                G.g[r+dr//2][c+dc//2]=EMPTY
                carve(nr,nc)
    carve(1,1)
    G.start=(1,1)
    G.goal=(G.r-2,G.c-2)
    G.g[G.start[0]][G.start[1]]=START
    G.g[G.goal[0]][G.goal[1]]=GOAL


def bfs(G,screen):
    start=G.start; goal=G.goal
    q=deque([start])
    came={start:None}
    seen={start}
    while q:
        cur=q.popleft()
        if cur!=start and cur!=goal:
            G.g[cur[0]][cur[1]]=CLOSED
        if cur==goal:
            return reconstruct(G,came)
        for nb in G.neighbors(*cur):
            if nb not in seen:
                seen.add(nb)
                came[nb]=cur
                q.append(nb)
                if nb!=start and nb!=goal:
                    G.g[nb[0]][nb[1]]=OPEN
        draw(screen,G)
    return []

def dfs(G,screen):
    stack=[G.start]
    came={G.start:None}
    seen={G.start}

    while stack:
        cur=stack.pop()
        if cur!=G.start and cur!=G.goal:
            G.g[cur[0]][cur[1]]=CLOSED
        if cur==G.goal:
            return reconstruct(G,came)
        for nb in G.neighbors(*cur):
            if nb not in seen:
                seen.add(nb)
                came[nb]=cur
                stack.append(nb)
                if nb!=G.start and nb!=G.goal:
                    G.g[nb[0]][nb[1]]=OPEN
        draw(screen,G)
    return []

def a_star(G,screen):
    h=lambda a,b:abs(a[0]-b[0])+abs(a[1]-b[1])
    start,goal=G.start,G.goal
    g={start:0}
    came={start:None}
    pq=[(h(start,goal),0,start)]
    open_s={start}
    while pq:
        _,cost,cur=heappop(pq)
        open_s.discard(cur)
        if cur!=start and cur!=goal:
            G.g[cur[0]][cur[1]]=CLOSED
        if cur==goal:
            return reconstruct(G,came)
        for nb in G.neighbors(*cur):
            t=cost+1
            if t<g.get(nb,1e9):
                g[nb]=t; came[nb]=cur
                f=t+h(nb,goal)
                if nb not in open_s:
                    heappush(pq,(f,t,nb))
                    open_s.add(nb)
                    if nb!=start and nb!=goal:
                        G.g[nb[0]][nb[1]]=OPEN
        draw(screen,G)
    return []



def reconstruct(G,came):
    cur=G.goal
    path=[]
    while cur:
        path.append(cur)
        cur=came[cur]
    path.reverse()
    return path


def draw(screen,G):
    screen.fill((30,30,30))
    for r in range(G.r):
        for c in range(G.c):
            rect=pygame.Rect(c*CELL,r*CELL,CELL,CELL)
            v=G.g[r][c]
            col=WHITE
            if v==WALL:col=BLACK
            elif v==START:col=BLUE
            elif v==GOAL:col=GREEN
            elif v==OPEN:col=GRAY
            elif v==CLOSED:col=PURPLE
            elif v==PATH:col=YELLOW
            elif v==PLAYER:col=ORANGE
            pygame.draw.rect(screen,col,rect)
            pygame.draw.rect(screen,(50,50,50),rect,1)
    pygame.display.flip()


def main():
    pygame.init()
    screen=pygame.display.set_mode((WIDTH,HEIGHT))
    pygame.display.set_caption("Treasure Hunt Game + Algorithm Visualization")
    clock=pygame.time.Clock()

    G=Grid(ROWS,COLS)
    algorithm="A*"

    running=True
    path=[]
    path_i=0

    while running:
        clock.tick(60)
        for e in pygame.event.get():
            if e.type==pygame.QUIT: running=False
            if e.type==pygame.KEYDOWN:
                if e.key==pygame.K_ESCAPE: running=False
                if e.key==pygame.K_1: algorithm="BFS"
                if e.key==pygame.K_2: algorithm="DFS"
                if e.key==pygame.K_3: algorithm="A*"
                if e.key==pygame.K_g: generate_maze(G)
                if e.key==pygame.K_r: G.reset(); path=[]
                if e.key==pygame.K_SPACE:
                    path=[]
                    G.reset()
                    if algorithm=="BFS":path=bfs(G,screen)
                    if algorithm=="DFS":path=dfs(G,screen)
                    if algorithm=="A*":path=a_star(G,screen)
                    for (r,c) in path:
                        if (r,c)!=G.start and (r,c)!=G.goal:
                            G.g[r][c]=PATH
                if e.key==pygame.K_RETURN and path:
                    
                    if path_i<len(path):
                        pr,pc=G.player
                        G.g[pr][pc]=EMPTY
                        nr,nc=path[path_i]
                        G.player=(nr,nc)
                        if (nr,nc)!=G.goal:
                            G.g[nr][nc]=PLAYER
                        path_i+=1

            if e.type==pygame.MOUSEBUTTONDOWN:
                mx,my=pygame.mouse.get_pos()
                if my>HEIGHT-50:continue
                c=mx//CELL; r=my//CELL
                if e.button==1:
                    mods=pygame.key.get_mods()
                    if mods & pygame.KMOD_SHIFT:
                        G.g[G.goal[0]][G.goal[1]]=EMPTY
                        G.goal=(r,c)
                        G.g[r][c]=GOAL
                    else:
                        if G.g[r][c]==WALL:G.g[r][c]=EMPTY
                        else:G.g[r][c]=WALL
                if e.button==3:
                    G.g[G.start[0]][G.start[1]]=EMPTY
                    G.start=(r,c); G.player=(r,c)
                    G.g[r][c]=START

        draw(screen,G)
    pygame.quit(); sys.exit()

if __name__=="__main__":
    main()



   