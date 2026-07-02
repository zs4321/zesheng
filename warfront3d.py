#!/usr/bin/env python3
"""
WARFRONT 3D - Raycasting FPS (pygame only, PyInstaller safe)
Features: save system, 2 modes, minimap, 3rd person, soldiers, BGM
"""
import pygame, sys, os, math, random, array, json
from pathlib import Path

# ═══════════════════════════════════════════════════════════════
W, H = 960, 600
BW, BH = W//2, H       # half-res render buffer
FPS = 60
FOV = math.pi / 3
NUM_RAYS = BW // 2
MAX_DEPTH = 55
BLACK=(0,0,0); WHITE=(255,255,255); RED=(220,40,40); DRED=(140,0,0)
YELLOW=(255,200,0); GREEN=(40,200,40); DGREEN=(20,100,20)
GRAY=(120,120,120); DGRAY=(60,60,60); VGRAY=(30,30,30); ORANGE=(255,140,0)
SAVE_FILE = Path.home() / ".warfront3d_save"

# ═══════════════════════════════════════════════════════════════
# SAVE SYSTEM
# ═══════════════════════════════════════════════════════════════
def load_save(name=""):
    if not name: return "", 0, 0, 0, [0]
    f = Path.home() / f".warfront3d_{name}.save"
    if f.exists():
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
            return d.get("name",name), d.get("unlocked",0), d.get("time",0), d.get("coins",0), d.get("warehouse",[0])
        except: pass
    return name, 0, 0, 0, [0]

def write_save(name, unlocked, playtime, coins=0, warehouse=None):
    if not name: return
    f = Path.home() / f".warfront3d_{name}.save"
    if warehouse is None: warehouse = [0]
    try:
        f.write_text(json.dumps({"name":name,"unlocked":unlocked,"time":playtime,"coins":coins,"warehouse":warehouse},
            ensure_ascii=False), encoding="utf-8")
    except: pass

# ═══════════════════════════════════════════════════════════════
# FONT
# ═══════════════════════════════════════════════════════════════
def detect_font():
    pygame.font.init()
    av = set(f.lower().replace(" ","") for f in pygame.font.get_fonts())
    for n in ("simhei","microsoftyahei","msyh","simsun","dengxian"):
        if n in av: return n
    return "arial"

# ═══════════════════════════════════════════════════════════════
# SOUND
# ═══════════════════════════════════════════════════════════════
def mk_wav(freq=440, dur=0.1, noise=0.5, vol=6000):
    sr=22050; n=int(sr*dur); s=[]
    for i in range(n):
        t=i/sr; env=max(0,1-t/dur)**1.5
        v=int(env*(random.randint(int(-vol*noise),int(vol*noise))+int(vol*(1-noise)*math.sin(2*math.pi*freq*t))))
        s.append(max(-32767,min(32767,v)))
    snd=pygame.mixer.Sound(buffer=array.array('h',s).tobytes()); snd.set_volume(0.5); return snd

def mk_bgm():
    """Generate a simple ambient loop."""
    sr=22050; dur=8; n=int(sr*dur); s=[]
    for i in range(n):
        t=i/sr
        v = int(1500*math.sin(2*math.pi*55*t) + 800*math.sin(2*math.pi*82*t)
              + 400*math.sin(2*math.pi*110*t*(1+0.1*math.sin(t*0.5))))
        env = min(1, t*2) * min(1, (dur-t)*2)  # fade in/out for loop
        s.append(max(-32767, min(32767, int(v*env*0.3))))
    snd=pygame.mixer.Sound(buffer=array.array('h',s).tobytes()); snd.set_volume(0.15); return snd

# ═══════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════
CN_FONT = None
def dtxt(s, txt, pos, sz=24, col=WHITE, bold=False, ctr=False, shd=True):
    f=pygame.font.SysFont(CN_FONT or "arial",sz,bold=bold)
    if shd:
        sh=f.render(txt,True,BLACK); r=sh.get_rect(center=pos) if ctr else sh.get_rect(topleft=pos)
        r.x+=2; r.y+=2; s.blit(sh,r)
    r2=f.render(txt,True,col); r=r2.get_rect(center=pos) if ctr else r2.get_rect(topleft=pos)
    s.blit(r2,r)

def dbar(s,x,y,w,h,ratio,col,bg=VGRAY):
    pygame.draw.rect(s,bg,(x,y,w,h)); pygame.draw.rect(s,col,(x+1,y+1,int((w-2)*max(0,min(1,ratio))),h-2))
    pygame.draw.rect(s,GRAY,(x,y,w,h),1)

# ═══════════════════════════════════════════════════════════════
# WEAPONS
# ═══════════════════════════════════════════════════════════════
WEAPONS=[
    {"name":"手枪","dmg":25,"rate":15,"mag":12,"reload":45,"auto":False,"spread":0.02,"pellets":1,"range":20},
    {"name":"突击步枪","dmg":16,"rate":5,"mag":30,"reload":60,"auto":True,"spread":0.04,"pellets":1,"range":25},
    {"name":"霰弹枪","dmg":12,"rate":25,"mag":6,"reload":75,"auto":False,"spread":0.12,"pellets":8,"range":10},
    {"name":"冲锋枪","dmg":11,"rate":3,"mag":40,"reload":50,"auto":True,"spread":0.06,"pellets":1,"range":18},
    {"name":"狙击枪","dmg":95,"rate":45,"mag":5,"reload":85,"auto":False,"spread":0.005,"pellets":1,"range":40},
]
WCOL=[(180,180,180),(160,140,100),(140,90,50),(100,100,140),(80,120,80)]

# ═══════════════════════════════════════════════════════════════
# ENEMIES
# ═══════════════════════════════════════════════════════════════
ETYPES={
    "basic":  {"hp":40,"spd":0.018,"dmg":8,"sc":100,"col":(80,120,60),"sz":0.55,"shoots":False,"det":12},
    "fast":   {"hp":25,"spd":0.035,"dmg":12,"sc":150,"col":(100,100,60),"sz":0.45,"shoots":False,"det":14},
    "shooter":{"hp":50,"spd":0.013,"dmg":10,"sc":200,"col":(60,80,50),"sz":0.55,"shoots":True,"det":16,"fr":70},
    "heavy":  {"hp":150,"spd":0.009,"dmg":18,"sc":350,"col":(50,60,40),"sz":0.7,"shoots":True,"det":14,"fr":50},
    "boss":   {"hp":400,"spd":0.013,"dmg":25,"sc":1000,"col":(40,20,20),"sz":1.0,"shoots":True,"det":20,"fr":30},
}

# ═══════════════════════════════════════════════════════════════
# LEVELS
# ═══════════════════════════════════════════════════════════════
LEVELS=[
    {"name":"训练场","waves":1,"en":[5,0,0,0,0],"th":(100,90,75),"ul":[1]},
    {"name":"城市废墟","waves":2,"en":[6,2,3,0,0],"th":(85,80,90),"ul":[]},
    {"name":"沙漠行动","waves":2,"en":[8,3,4,1,0],"th":(130,110,65),"ul":[2]},
    {"name":"夜间突袭","waves":3,"en":[10,4,5,2,0],"th":(40,45,65),"ul":[3]},
    {"name":"丛林战斗","waves":3,"en":[12,5,6,3,0],"th":(55,90,55),"ul":[]},
    {"name":"雪山要塞","waves":3,"en":[12,6,7,4,0],"th":(90,95,115),"ul":[4]},
    {"name":"地狱前线","waves":4,"en":[14,7,8,5,0],"th":(95,50,50),"ul":[]},
    {"name":"末日之战","waves":4,"en":[14,8,9,6,1],"th":(75,35,40),"ul":[]},
    {"name":"最终决战","waves":5,"en":[18,10,12,8,2],"th":(60,25,35),"ul":[]},
]

# ═══════════════════════════════════════════════════════════════
# MAP GENERATION
# ═══════════════════════════════════════════════════════════════
def gen_level_map(seed):
    S=32; random.seed(seed*137+42)
    g=[[0]*S for _ in range(S)]
    for i in range(S): g[0][i]=g[S-1][i]=g[i][0]=g[i][S-1]=1
    for _ in range(6+seed*2):
        sh=random.choice(["box","wall","L"])
        sx,sy=random.randint(3,S-8),random.randint(3,S-8)
        cx,cy=S//2,S//2
        if abs(sx-cx)<3 and abs(sy-cy)<3: continue
        if sh=="box":
            bw,bh=random.randint(2,4),random.randint(2,4)
            for dx in range(bw):
                for dy in range(bh):
                    if 0<sx+dx<S-1 and 0<sy+dy<S-1:
                        if dx==0 or dx==bw-1 or dy==0 or dy==bh-1: g[sy+dy][sx+dx]=1
        elif sh=="wall":
            ln=random.randint(3,7); vert=random.choice([True,False])
            for d in range(ln):
                nx,ny=(sx,sy+d) if vert else (sx+d,sy)
                if 0<nx<S-1 and 0<ny<S-1: g[ny][nx]=1
        elif sh=="L":
            for dx in range(4):
                if 0<sx+dx<S-1: g[sy][sx+dx]=1
            for dy in range(1,4):
                if 0<sy+dy<S-1: g[sy+dy][sx+3]=1
    for dx in range(-2,3):
        for dy in range(-2,3):
            px,py=cx+dx,cy+dy
            if 0<px<S-1 and 0<py<S-1: g[py][px]=0
    random.seed(); return g, S

def gen_classic_map():
    S=100; random.seed(42)
    g=[[0]*S for _ in range(S)]
    # Border walls
    for i in range(S): g[0][i]=g[S-1][i]=g[i][0]=g[i][S-1]=1
    # Scattered ruins
    for _ in range(25):
        sh=random.choice(["ruin","wall","tower"])
        sx,sy=random.randint(5,S-15),random.randint(5,S-15)
        cx,cy=S//2,S//2
        if abs(sx-cx)<6 and abs(sy-cy)<6: continue
        if sh=="ruin":
            bw,bh=random.randint(3,6),random.randint(3,6)
            for dx in range(bw):
                for dy in range(bh):
                    if 0<sx+dx<S-1 and 0<sy+dy<S-1:
                        if random.random()<0.4 and (dx==0 or dx==bw-1 or dy==0 or dy==bh-1):
                            g[sy+dy][sx+dx]=1
        elif sh=="wall":
            ln=random.randint(4,12); vert=random.choice([True,False])
            for d in range(ln):
                nx,ny=(sx,sy+d) if vert else (sx+d,sy)
                if 0<nx<S-1 and 0<ny<S-1: g[ny][nx]=1
        elif sh=="tower":
            for dx in range(3):
                for dy in range(3):
                    if 0<sx+dx<S-1 and 0<sy+dy<S-1: g[sy+dy][sx+dx]=1
    # Decorative tiles (2=grass, 3=flower, 4=bush, 5=rock)
    for _ in range(300):
        x,y=random.randint(2,S-3),random.randint(2,S-3)
        if g[y][x]==0: g[y][x]=random.choice([2,2,2,3,3,4,4,5])
    # Clear spawn
    for dx in range(-4,5):
        for dy in range(-4,5):
            px,py=cx+dx,cy+dy
            if 0<px<S-1 and 0<py<S-1: g[py][px]=0
    random.seed(); return g, S

# ═══════════════════════════════════════════════════════════════
# RAYCASTING
# ═══════════════════════════════════════════════════════════════
def cast_rays(px, py, pa, world, MS):
    rays=[]; zbuf=[]
    cos_pa=math.cos(pa); sin_pa=math.sin(pa)
    for i in range(NUM_RAYS):
        angle = pa - FOV/2 + (i/NUM_RAYS)*FOV
        ra_cos=math.cos(angle); ra_sin=math.sin(angle)
        if abs(ra_cos)<1e-10: ra_cos=1e-10
        if abs(ra_sin)<1e-10: ra_sin=1e-10

        mx=int(px); my=int(py)
        ddx=abs(1/ra_cos); ddy=abs(1/ra_sin)
        if ra_cos<0: sx=-1; sdx=(px-mx)*ddx
        else:        sx=1;  sdx=(mx+1-px)*ddx
        if ra_sin<0: sy=-1; sdy=(py-my)*ddy
        else:        sy=1;  sdy=(my+1-py)*ddy

        hit=False; side=0
        for _ in range(120):
            if sdx<sdy: sdx+=ddx; mx+=sx; side=0
            else:       sdy+=ddy; my+=sy; side=1
            if mx<0 or mx>=MS or my<0 or my>=MS: hit=True; break
            if world[my][mx]==1: hit=True; break

        dist = (sdx-ddx) if side==0 else (sdy-ddy)
        dist=max(dist,0.01)
        corr=dist*math.cos(angle-pa)
        rays.append((corr, side, mx, my))
        zbuf.append(corr)
    return rays, zbuf

# ═══════════════════════════════════════════════════════════════
# SOLDIER SPRITE DRAWING
# ═══════════════════════════════════════════════════════════════
def draw_soldier(buf, cx, top, sw, sh, col, alive, etype, shade):
    c=tuple(max(0,min(255,int(v*shade))) for v in col)
    boot=(max(0,c[0]-30),max(0,c[1]-30),max(0,c[2]-20))
    skin=(min(255,c[0]+60),min(255,c[1]+40),min(255,c[2]+30))
    gun=(50,50,55)

    if not alive:
        pygame.draw.rect(buf,c,(cx-sh//2,top+sh-sh//4,sh,sw//2))
        return

    leg_h=int(sh*0.35); body_h=int(sh*0.35); head_h=int(sh*0.2)
    leg_w=max(1,sw//4); body_w=max(1,int(sw*0.45)); head_w=max(1,int(sw*0.3))
    y=top
    # Head
    pygame.draw.rect(buf,skin,(cx-head_w//2,y,head_w,head_h))
    pygame.draw.rect(buf,boot,(cx-head_w//2-1,y,head_w+2,head_h//3)) # helmet
    y+=head_h
    # Body
    pygame.draw.rect(buf,c,(cx-body_w//2,y,body_w,body_h))
    # Arms + gun
    arm_y=y+body_h//4
    gun_len=max(2,sw//2)
    pygame.draw.line(buf,gun,(cx+body_w//2,arm_y),(cx+body_w//2+gun_len,arm_y),max(1,sw//10))
    pygame.draw.line(buf,skin,(cx-body_w//2,arm_y),(cx-body_w//2-sw//6,arm_y+body_h//4),max(1,sw//12))
    y+=body_h
    # Legs
    pygame.draw.rect(buf,boot,(cx-leg_w-1,y,leg_w,leg_h))
    pygame.draw.rect(buf,boot,(cx+1,y,leg_w,leg_h))

# ═══════════════════════════════════════════════════════════════
# GAME
# ═══════════════════════════════════════════════════════════════
class Game:
    def __init__(self):
        pygame.init()
        pygame.mixer.init(frequency=22050,size=-16,channels=1,buffer=512)
        global CN_FONT; CN_FONT=detect_font()
        self.screen=pygame.display.set_mode((W,H))
        pygame.display.set_caption("WARFRONT 3D")
        self.clock=pygame.time.Clock()
        self.running=True; self.t=0
        self.buf=pygame.Surface((BW,H))

        # Menu background images
        self.menu_sky=None; self.menu_ground=None; self.menu_ruins=None
        try:
            base = r"C:\Users\zesheng\Desktop\games\warfont3D\menu_assets"
            self.menu_sky = pygame.image.load(os.path.join(base, "sky.png")).convert()
            self.menu_ground = pygame.image.load(os.path.join(base, "ground.png")).convert()
            self.menu_ruins = pygame.image.load(os.path.join(base, "ruins.png")).convert_alpha()
        except Exception:
            pass

        # Init state (empty, will load on login)
        self.user_name = ""
        self.max_ul = 0
        self.playtime = 0
        self.coins = 0
        self.warehouse = [0]
        self.name_buf = ""
        self.state = "LOGIN"

        # Sounds
        try:
            self.snd=[mk_wav(200,0.12,0.7,8000),mk_wav(100,0.25,0.9,12000),
                       mk_wav(60,0.5,0.85,10000),mk_wav(800,0.06,0.3,5000),mk_wav(1200,0.15,0.2,3000)]
            self.bgm=mk_bgm(); self.bgm.play(-1)
        except: self.snd=[]; self.bgm=None

        # State
        self.mode="level"  # "level" or "classic"
        self.tp=False  # third person toggle
        self.minimap_big=False

        self.weapons=[0]
        self.ws_selected=set()
        self.pending_level=None

        # Cover particles
        self.cparts=[{"x":random.randint(0,W),"y":random.randint(0,H),
            "vx":random.uniform(-0.3,0.3),"vy":random.uniform(-1,-0.2),
            "sz":random.uniform(1,3),"a":random.uniform(0.1,0.4)} for _ in range(50)]

        self.reset()

    def reset(self):
        self.px=16; self.py=16; self.pa=0; self.view_pa=0
        self.hp=100; self.max_hp=100
        self.cur_w=0
        self.ammo={wk:WEAPONS[wk]["mag"] for wk in self.warehouse}
        self.reserve={wk:WEAPONS[wk]["mag"]*3 for wk in self.warehouse}
        self.fcd=0; self.rld=0; self.grenades=3
        self.score=0; self.kills=0
        self.clvl=0; self.cwave=0; self.twaves=0; self.wdly=0
        self.inv=0; self.regt=0; self.enemies=[]
        self.glist=[]; self.floats=[]; self.world=None; self.MS=32
        self.shake=0; self.muzzle=0; self.recoil=0; self.dflash=0
        self.bob=0
        self.jump_y=0; self.vjump=0

    # ─── LOOP ──────────────────────────────────────────────
    def run(self):
        while self.running:
            self.clock.tick(FPS)
            self.events(); self.update(); self.draw()
            pygame.display.flip()
        pygame.quit()

    # ─── EVENTS ────────────────────────────────────────────
    def events(self):
        for e in pygame.event.get():
            if e.type==pygame.QUIT: self.running=False
            elif e.type==pygame.TEXTINPUT:
                if self.state=="LOGIN" and e.text and len(self.name_buf)<16:
                    self.name_buf+=e.text
            elif e.type==pygame.KEYDOWN:
                if self.state=="LOGIN":
                    if e.key==pygame.K_RETURN and self.name_buf.strip():
                        self.user_name=self.name_buf.strip()
                        _, self.max_ul, self.playtime, self.coins, self.warehouse = load_save(self.user_name)
                        if not self.warehouse: self.warehouse=[0]
                        self.state="MENU"
                    elif e.key==pygame.K_BACKSPACE: self.name_buf=self.name_buf[:-1]
                    elif e.key==pygame.K_ESCAPE: self.running=False
                    # Physical key fallback for IME Chinese input mode
                    elif e.key >= pygame.K_a and e.key <= pygame.K_z:
                        if len(self.name_buf)<16: self.name_buf+=chr(ord('a') + e.key - pygame.K_a)
                    elif e.key >= pygame.K_0 and e.key <= pygame.K_9:
                        if len(self.name_buf)<16: self.name_buf+=chr(ord('0') + e.key - pygame.K_0)
                    elif e.key == pygame.K_SPACE:
                        if len(self.name_buf)<16: self.name_buf+=" "
                elif self.state=="MENU":
                    if e.key==pygame.K_1: self.mode="level"; self.state="SELECT"
                    elif e.key==pygame.K_2:
                        self.mode="classic"; self.pending_level=-1
                        self.ws_selected=set(self.warehouse); self.state="WEAPON_SELECT"
                    elif e.key==pygame.K_ESCAPE: self.running=False
                elif self.state=="SELECT":
                    if e.key==pygame.K_ESCAPE: self.state="MENU"
                elif self.state=="WEAPON_SELECT":
                    if e.key==pygame.K_ESCAPE:
                        self.state="SELECT" if self.pending_level!=-1 else "MENU"
                    elif e.key==pygame.K_RETURN and len(self.ws_selected)>0:
                        if self.pending_level==-1: self.start_classic()
                        else: self.start_level(self.pending_level)
                elif self.state=="WAREHOUSE":
                    if e.key in (pygame.K_ESCAPE,pygame.K_RETURN): self.state="MENU"
                elif self.state=="SHOP":
                    if e.key in (pygame.K_ESCAPE,pygame.K_RETURN): self.state="MENU"
                elif self.state in ("DEAD","WIN"):
                    if e.key in (pygame.K_RETURN,pygame.K_SPACE):
                        self.state="MENU" if self.mode=="classic" else "SELECT"
                    elif e.key==pygame.K_ESCAPE: self.state="MENU"
                elif self.state=="PLAY":
                    if e.key==pygame.K_ESCAPE: self.state="SELECT" if self.mode=="level" else "MENU"
                    if e.key==pygame.K_v: self.tp=not self.tp
                    if e.key==pygame.K_m: self.minimap_big=not self.minimap_big
                    if e.key==pygame.K_r and self.rld<=0:
                        w=WEAPONS[self.weapons[self.cur_w]]; wk=self.weapons[self.cur_w]
                        if self.ammo[wk]<w["mag"] and self.reserve[wk]>0:
                            self.rld=w["reload"]
                            if len(self.snd)>4: self.snd[4].play()
                    if e.key==pygame.K_SPACE and self.jump_y<=0:
                        self.vjump=4.0
                    for i in range(1,6):
                        if e.key==getattr(pygame,f"K_{i}",-1) and i-1<len(self.weapons):
                            self.cur_w=i-1; self.rld=0
            elif e.type==pygame.MOUSEBUTTONDOWN:
                if self.state=="PLAY":
                    if e.button==1: self.shoot()
                    elif e.button==3: self.throw_gren()
                    elif e.button==4 and self.minimap_big is not None:
                        # Check minimap click
                        mx,my=pygame.mouse.get_pos()
                        if mx>W-170 and my<170: self.minimap_big=not self.minimap_big
                elif self.state=="SELECT":
                    self._select_click()
                elif self.state=="MENU":
                    self._menu_click()
                elif self.state=="WAREHOUSE":
                    self._warehouse_click()
                elif self.state=="SHOP":
                    self._shop_click()
                elif self.state=="WEAPON_SELECT":
                    self._weapon_select_click()
            elif e.type==pygame.MOUSEWHEEL and self.state=="PLAY":
                d=1 if e.y>0 else -1
                self.cur_w=(self.cur_w+d)%len(self.weapons); self.rld=0

    def _select_click(self):
        mx,my=pygame.mouse.get_pos(); gx0=W//2-340; gy0=160
        for i in range(9):
            c,r=i%3,i//3; rx,ry=gx0+c*240,gy0+r*140
            if rx<mx<rx+210 and ry<my<ry+115 and i<=self.max_ul:
                self.pending_level=i; self.ws_selected=set(self.warehouse)
                self.state="WEAPON_SELECT"

    def _menu_click(self):
        mx, my = pygame.mouse.get_pos()
        # Level challenge button
        bx, by = W//2-220, 280
        if bx < mx < bx+200 and by < my < by+160:
            self.mode = "level"; self.state = "SELECT"
        # Classic mode button
        bx2 = W//2+20
        if bx2 < mx < bx2+200 and by < my < by+160:
            self.mode = "classic"; self.pending_level = -1
            self.ws_selected = set(self.warehouse); self.state = "WEAPON_SELECT"
        # My Warehouse button (under level challenge)
        wx, wy = bx, by+180
        if wx < mx < wx+200 and wy < my < wy+60:
            self.state = "WAREHOUSE"
        # Shop button (under classic mode)
        sx, sy = bx2, by+180
        if sx < mx < sx+200 and sy < my < sy+60:
            self.state = "SHOP"
        # Exit login button (bottom-right corner)
        ex_x, ex_y = W-130, H-80
        if ex_x < mx < ex_x+120 and ex_y < my < ex_y+35:
            write_save(self.user_name, self.max_ul, self.playtime, self.coins, self.warehouse)
            self.user_name = ""
            self.name_buf = ""
            self.max_ul = 0
            self.playtime = 0
            self.coins = 0
            self.warehouse = [0]
            self.state = "LOGIN"

    def _draw_warehouse(self):
        self.screen.fill((18,18,22))
        for x in range(0,W,40): pygame.draw.line(self.screen,(25,25,30),(x,0),(x,H))
        for y in range(0,H,40): pygame.draw.line(self.screen,(25,25,30),(0,y),(W,y))
        dtxt(self.screen,"我的仓库",(W//2,50),38,WHITE,True,True)
        pygame.draw.line(self.screen,YELLOW,(W//2-180,85),(W//2+180,85),2)

        # Draw owned weapons list
        gx0=W//2-340; gy0=120
        for i,wk in enumerate(self.warehouse):
            c,r=i%3,i//3; rx,ry=gx0+c*240,gy0+r*140
            rw,rh=215,115
            w=WEAPONS[wk]
            mx,my=pygame.mouse.get_pos()
            hvr=rx<mx<rx+rw and ry<my<ry+rh
            bg=(55,55,65) if hvr else (40,40,48)
            bdr=YELLOW if hvr else GRAY
            pygame.draw.rect(self.screen,bg,(rx,ry,rw,rh),border_radius=8)
            pygame.draw.rect(self.screen,bdr,(rx,ry,rw,rh),2 if hvr else 1,border_radius=8)
            dtxt(self.screen,w["name"],(rx+rw//2,ry+18),20,WHITE,True,True,False)
            dtxt(self.screen,f"伤害: {w['dmg']}",(rx+12,ry+45),13,GRAY,shd=False)
            dtxt(self.screen,f"射速: {w['rate']}",(rx+12,ry+62),13,GRAY,shd=False)
            dtxt(self.screen,f"弹匣: {w['mag']}",(rx+12,ry+79),13,GRAY,shd=False)
            dtxt(self.screen,f"备弹: {self.ammo.get(wk,0)}/{self.reserve.get(wk,0)}",(rx+12,ry+96),13,YELLOW,shd=False)
            # weapon type indicator
            wc=WCOL[wk]
            pygame.draw.rect(self.screen,wc,(rx+rw-30,ry+10,16,16),border_radius=3)

        # Bottom bar
        for i in range(35):
            y=H-35+i; r=i/35
            c=(int(YELLOW[0]*(1-r*0.7)),int(YELLOW[1]*(1-r*0.7)),int(YELLOW[2]*(1-r*0.7)))
            pygame.draw.line(self.screen,c,(0,y),(W,y))
        for x in range(-35,W+35,50):
            pygame.draw.polygon(self.screen,BLACK,[(x,H-35),(x+25,H-35),(x+40,H),(x+15,H)])
        dtxt(self.screen,"ESC 返回菜单 | ENTER 进入菜单",(W//2,H-22),15,BLACK,True,True,False)

    def _draw_weapon_select(self):
        self.screen.fill((18,18,22))
        for x in range(0,W,40): pygame.draw.line(self.screen,(25,25,30),(x,0),(x,H))
        for y in range(0,H,40): pygame.draw.line(self.screen,(25,25,30),(0,y),(W,y))
        dtxt(self.screen,"选择武器",(W//2,50),38,WHITE,True,True)
        pygame.draw.line(self.screen,YELLOW,(W//2-180,85),(W//2+180,85),2)

        # Draw warehouse weapons
        gx0=W//2-340; gy0=120
        for i,wk in enumerate(self.warehouse):
            c,r=i%3,i//3; rx,ry=gx0+c*240,gy0+r*140
            rw,rh=215,115
            w=WEAPONS[wk]
            selected=wk in self.ws_selected
            mx,my=pygame.mouse.get_pos()
            hvr=rx<mx<rx+rw and ry<my<ry+rh
            bg=(55,55,65) if hvr and selected else (40,40,48) if selected else (25,25,28)
            bdr=YELLOW if selected else GRAY
            pygame.draw.rect(self.screen,bg,(rx,ry,rw,rh),border_radius=8)
            pygame.draw.rect(self.screen,bdr,(rx,ry,rw,rh),2 if selected else 1,border_radius=8)
            if selected:
                pygame.draw.circle(self.screen,YELLOW,(rx+rw-20,ry+20),10)
                dtxt(self.screen,"✓",(rx+rw-20,ry+20),14,BLACK,True,True,False)
            dtxt(self.screen,w["name"],(rx+rw//2,ry+18),20,WHITE,True,True,False)
            dtxt(self.screen,f"伤害: {w['dmg']}",(rx+12,ry+45),13,GRAY,shd=False)
            dtxt(self.screen,f"射速: {w['rate']}",(rx+12,ry+62),13,GRAY,shd=False)
            dtxt(self.screen,f"弹匣: {w['mag']}",(rx+12,ry+79),13,GRAY,shd=False)
            wc=WCOL[wk]
            pygame.draw.rect(self.screen,wc,(rx+rw-30,ry+40,16,16),border_radius=3)

        # Start button
        btn_x,btn_y=W//2-100,H-100
        has_sel=len(self.ws_selected)>0
        mx,my=pygame.mouse.get_pos()
        btn_hvr=btn_x<mx<btn_x+200 and btn_y<my<btn_y+50
        btn_bg=(80,60,30) if btn_hvr and has_sel else (50,40,25) if has_sel else (35,35,35)
        btn_bdr=YELLOW if btn_hvr and has_sel else GRAY if has_sel else (60,60,60)
        pygame.draw.rect(self.screen,btn_bg,(btn_x,btn_y,200,50),border_radius=8)
        pygame.draw.rect(self.screen,btn_bdr,(btn_x,btn_y,200,50),2,border_radius=8)
        btn_col=WHITE if has_sel else (80,80,80)
        dtxt(self.screen,"开始战斗",(btn_x+100,btn_y+25),20,btn_col,True,True,False)
        if not has_sel:
            dtxt(self.screen,"请至少选择一把武器",(W//2,btn_y-15),14,RED,True,True)

        dtxt(self.screen,"ESC 返回 | 点击武器切换选择",(W//2,H-22),15,GRAY,True,True)

    def _weapon_select_click(self):
        mx,my=pygame.mouse.get_pos()
        gx0=W//2-340; gy0=120
        for i,wk in enumerate(self.warehouse):
            c,r=i%3,i//3; rx,ry=gx0+c*240,gy0+r*140
            rw,rh=215,115
            if rx<mx<rx+rw and ry<my<ry+rh:
                if wk in self.ws_selected:
                    if len(self.ws_selected)>1:
                        self.ws_selected.remove(wk)
                else:
                    self.ws_selected.add(wk)
                return
        # Start button
        btn_x,btn_y=W//2-100,H-100
        if btn_x<mx<btn_x+200 and btn_y<my<btn_y+50 and len(self.ws_selected)>0:
            if self.pending_level==-1: self.start_classic()
            else: self.start_level(self.pending_level)

    def _warehouse_click(self):
        mx, my = pygame.mouse.get_pos()
        self.state = "MENU"

    def _draw_shop(self):
        self.screen.fill((18, 18, 22))
        for x in range(0, W, 40):
            pygame.draw.line(self.screen, (25, 25, 30), (x, 0), (x, H))
        for y in range(0, H, 40):
            pygame.draw.line(self.screen, (25, 25, 30), (0, y), (W, y))
        dtxt(self.screen, "武 器 商 店", (W // 2, 50), 38, WHITE, True, True)
        pygame.draw.line(self.screen, YELLOW, (W // 2 - 180, 85), (W // 2 + 180, 85), 2)
        dtxt(self.screen, f"金币: {self.coins}", (W - 100, 50), 18, YELLOW, True, True, False)

        # Draw shop items
        prices = [15, 25, 20, 25, 30]
        gx0 = W // 2 - 340
        gy0 = 120
        for i, wk in enumerate(range(5)):
            c, r = i % 3, i // 3
            rx, ry = gx0 + c * 240, gy0 + r * 140
            rw, rh = 215, 115
            w = WEAPONS[wk]
            mx, my = pygame.mouse.get_pos()
            hvr = rx < mx < rx + rw and ry < my < ry + rh
            bg = (55, 55, 65) if hvr else (40, 40, 48)
            bdr = YELLOW if hvr else GRAY
            pygame.draw.rect(self.screen, bg, (rx, ry, rw, rh), border_radius=8)
            pygame.draw.rect(self.screen, bdr, (rx, ry, rw, rh), 2 if hvr else 1, border_radius=8)
            dtxt(self.screen, w["name"], (rx + rw // 2, ry + 18), 20, WHITE, True, True, False)
            dtxt(self.screen, f"伤害: {w['dmg']}", (rx + 12, ry + 45), 13, GRAY, shd=False)
            dtxt(self.screen, f"弹匣: {w['mag']}", (rx + 12, ry + 62), 13, GRAY, shd=False)
            dtxt(self.screen, f"备弹: {self.ammo.get(wk, 0)}/{self.reserve.get(wk, 0)}", (rx + 12, ry + 79), 13, YELLOW, shd=False)
            dtxt(self.screen, f"{prices[wk]} 金币", (rx + 12, ry + 96), 12, YELLOW, shd=False)
            wc = WCOL[wk]
            pygame.draw.rect(self.screen, wc, (rx + rw - 30, ry + 10, 16, 16), border_radius=3)

        # Grenade shop card
        grx, gry = W // 2 - 100, 400
        grw, grh = 200, 80
        mx, my = pygame.mouse.get_pos()
        gr_hvr = grx < mx < grx + grw and gry < my < gry + grh
        gr_bg = (55, 55, 65) if gr_hvr else (40, 40, 48)
        gr_bdr = YELLOW if gr_hvr else GRAY
        pygame.draw.rect(self.screen, gr_bg, (grx, gry, grw, grh), border_radius=8)
        pygame.draw.rect(self.screen, gr_bdr, (grx, gry, grw, grh), 2 if gr_hvr else 1, border_radius=8)
        dtxt(self.screen, "手榴弹", (grx + grw // 2, gry + 20), 20, WHITE, True, True, False)
        dtxt(self.screen, f"当前: {self.grenades} 个", (grx + grw // 2, gry + 50), 14, YELLOW, True, True)
        dtxt(self.screen, "40 金币", (grx + grw // 2, gry + 65), 12, YELLOW, True, True)

        # Bottom bar
        for i in range(35):
            y = H - 35 + i
            r = i / 35
            c = (int(YELLOW[0] * (1 - r * 0.7)), int(YELLOW[1] * (1 - r * 0.7)), int(YELLOW[2] * (1 - r * 0.7)))
            pygame.draw.line(self.screen, c, (0, y), (W, y))
        for x in range(-35, W + 35, 50):
            pygame.draw.polygon(self.screen, BLACK, [(x, H - 35), (x + 25, H - 35), (x + 40, H), (x + 15, H)])
        dtxt(self.screen, "ESC 返回菜单", (W // 2, H - 22), 15, BLACK, True, True, False)

    def _shop_click(self):
        mx, my = pygame.mouse.get_pos()
        prices = [15, 25, 20, 25, 30]
        # Weapon ammo purchase
        gx0 = W // 2 - 340
        gy0 = 120
        for i, wk in enumerate(range(5)):
            c, r = i % 3, i // 3
            rx, ry = gx0 + c * 240, gy0 + r * 140
            rw, rh = 215, 115
            if rx < mx < rx + rw and ry < my < ry + rh:
                if self.coins >= prices[wk]:
                    self.coins -= prices[wk]
                    self.reserve[wk] = self.reserve.get(wk, 0) + WEAPONS[wk]["mag"]
                return
        # Grenade purchase
        grx, gry = W // 2 - 100, 400
        grw, grh = 200, 80
        if grx < mx < grx + grw and gry < my < gry + grh:
            if self.coins >= 40:
                self.coins -= 40
                self.grenades = min(self.grenades + 1, 10)

    # ─── UPDATE ────────────────────────────────────────────
    def update(self):
        self.t+=1; self.playtime+=1/60
        if self.t%3600==0: write_save(self.user_name,self.max_ul,int(self.playtime),self.coins,self.warehouse)
        if self.state=="LOGIN": pass
        elif self.state=="MENU": self._update_cover()
        elif self.state=="SELECT": pass
        elif self.state=="PLAY": self._update_play()

    def _update_cover(self):
        for p in self.cparts:
            p["x"]+=p["vx"]; p["y"]+=p["vy"]
            if p["y"]<-5: p["y"]=H+5; p["x"]=random.randint(0,W)

    def _update_play(self):
        keys=pygame.key.get_pressed()
        spd=0.06
        mx,my=pygame.mouse.get_pos()

        # Mouse look
        mdx=mx-W//2
        self.pa+=mdx*0.003
        self.view_pa=self.pa
        pygame.mouse.set_pos(W//2,H//2)

        # Movement
        nx,ny=self.px,self.py
        cos,sin=math.cos(self.pa),math.sin(self.pa)
        moved=False
        if keys[pygame.K_w] or keys[pygame.K_UP]:    nx+=cos*spd; ny+=sin*spd; moved=True
        if keys[pygame.K_s] or keys[pygame.K_DOWN]:   nx-=cos*spd; ny-=sin*spd; moved=True
        if keys[pygame.K_a] or keys[pygame.K_LEFT]:   nx+=sin*spd; ny-=cos*spd; moved=True
        if keys[pygame.K_d] or keys[pygame.K_RIGHT]:  nx-=sin*spd; ny+=cos*spd; moved=True
        if moved: self.bob+=0.15

        m=0.25
        cx,cy=int(nx),int(ny)
        if 0<=cx<self.MS and 0<=int(self.py)<self.MS:
            if self.world[int(self.py)][min(self.MS-1,max(0,int(nx+m)))]==0 and \
               self.world[int(self.py)][min(self.MS-1,max(0,int(nx-m)))]==0 and \
               (self.world[int(self.py)][cx]==0 or self.world[int(self.py)][cx]>=2):
                self.px=nx
        if 0<=int(self.px)<self.MS and 0<=cy<self.MS:
            if self.world[min(self.MS-1,max(0,int(ny+m)))][int(self.px)]==0 and \
               self.world[min(self.MS-1,max(0,int(ny-m)))][int(self.px)]==0 and \
               (self.world[cy][int(self.px)]==0 or self.world[cy][int(self.px)]>=2):
                self.py=ny

        # Jump physics
        if self.vjump>0 or self.jump_y>0:
            self.jump_y+=self.vjump
            self.vjump-=0.15
            if self.jump_y<=0:
                self.jump_y=0; self.vjump=0

        # Timers
        self.fcd=max(0,self.fcd-1); self.inv=max(0,self.inv-1)
        self.muzzle=max(0,self.muzzle-1); self.recoil=max(0,self.recoil-0.5)
        self.dflash=max(0,self.dflash-2)
        if self.shake>0: self.shake*=0.85
        if self.shake<0.3: self.shake=0

        if self.rld>0:
            self.rld-=1
            if self.rld==0:
                wk=self.weapons[self.cur_w]; w=WEAPONS[wk]
                need=w["mag"]-self.ammo[wk]; give=min(need,self.reserve[wk])
                self.ammo[wk]+=give; self.reserve[wk]-=give

        if self.regt>0: self.regt-=1
        elif self.hp<self.max_hp and self.hp>0: self.hp=min(self.max_hp,self.hp+0.08)

        if pygame.mouse.get_pressed()[0] and WEAPONS[self.weapons[self.cur_w]]["auto"]:
            self.shoot()

        # Enemies
        for e in self.enemies:
            if e["alive"]: self._upd_enemy(e)
            else: e["dt"]+=1
        self.enemies=[e for e in self.enemies if e["alive"] or e["dt"]<60]

        # Grenades
        ng=[]
        for g in self.glist:
            g["t"]-=1; g["x"]+=g["vx"]; g["y"]+=g["vy"]
            g["vx"]*=0.96; g["vy"]*=0.96
            if g["t"]<=0: self._explode(g["x"],g["y"])
            else: ng.append(g)
        self.glist=ng

        self.floats=[f for f in self.floats if f["t"]>0]
        for f in self.floats: f["t"]-=1

        # Waves
        alive=sum(1 for e in self.enemies if e["alive"])
        if alive==0 and self.wdly<=0 and self.cwave<self.twaves:
            self._spawn_wave(); self.wdly=120
        if self.wdly>0: self.wdly-=1

        if self.hp<=0:
            self.state="DEAD"
            write_save(self.user_name,self.max_ul,int(self.playtime),self.coins,self.warehouse)
        if self.cwave>=self.twaves and alive==0 and self.wdly<=0:
            self.state="WIN"
            if self.mode=="level":
                diff=min(5,self.clvl//2+1)
                self.coins+=diff*50
                if self.clvl>=self.max_ul:
                    self.max_ul=min(8,self.clvl+1)
            else:
                self.coins+=100
            write_save(self.user_name,self.max_ul,int(self.playtime),self.coins,self.warehouse)

    def _upd_enemy(self,e):
        dx=self.px-e["x"]; dy=self.py-e["y"]; d=math.hypot(dx,dy)
        if d<0.1: return
        et=ETYPES[e["type"]]
        if d>1.2:
            nx=e["x"]+(dx/d)*et["spd"]; ny=e["y"]+(dy/d)*et["spd"]
            nix,niy=int(nx),int(ny)
            if 0<=nix<self.MS and 0<=niy<self.MS:
                t=self.world[niy][nix]
                if t==0 or t>=2: e["x"]=nx; e["y"]=ny
        if et["shoots"] and d<et["det"]:
            e["fc"]-=1
            if e["fc"]<=0:
                e["fc"]=et["fr"]
                if random.random()<max(0.1,0.5-d*0.03) and self.inv<=0:
                    self.hp-=et["dmg"]; self.inv=15; self.regt=120; self.dflash=60; self.shake=5
        if not et["shoots"] and d<0.8 and self.inv<=0:
            self.hp-=et["dmg"]; self.inv=20; self.regt=120; self.dflash=60; self.shake=6

    # ─── ACTIONS ───────────────────────────────────────────
    def shoot(self):
        if self.fcd>0 or self.rld>0: return
        wk=self.weapons[self.cur_w]; w=WEAPONS[wk]
        if self.ammo[wk]<=0:
            if self.reserve[wk]>0: self.rld=w["reload"]
            return
        self.ammo[wk]-=1; self.fcd=w["rate"]; self.muzzle=4; self.recoil=3
        if len(self.snd)>1:
            (self.snd[1] if wk==2 else self.snd[0]).play()

        for _ in range(w["pellets"]):
            spread=random.uniform(-w["spread"],w["spread"])
            angle=self.pa+spread; best=w["range"]; hit_e=None
            for e in self.enemies:
                if not e["alive"]: continue
                ed=math.hypot(e["x"]-self.px,e["y"]-self.py)
                if ed>w["range"]: continue
                ea=math.atan2(e["y"]-self.py,e["x"]-self.px)
                diff=abs(((ea-angle+math.pi)%(2*math.pi))-math.pi)
                hw=0.4/max(ed,0.5)
                if diff<hw and ed<best:
                    wd=self._ray_dist(angle)
                    if ed<wd: best=ed; hit_e=e
            if hit_e:
                hit_e["hp"]-=w["dmg"]
                self.floats.append({"x":hit_e["x"],"y":hit_e["y"],"txt":str(w["dmg"]),"t":40,"col":YELLOW})
                if len(self.snd)>3: self.snd[3].play()
                if hit_e["hp"]<=0:
                    hit_e["alive"]=False; hit_e["dt"]=0
                    self.kills+=1; self.score+=ETYPES[hit_e["type"]]["sc"]

    def _ray_dist(self,angle):
        cos,sin=math.cos(angle),math.sin(angle); x,y=self.px,self.py
        for _ in range(int(MAX_DEPTH/0.05)):
            x+=cos*0.05; y+=sin*0.05
            mx,my=int(x),int(y)
            if mx<0 or mx>=self.MS or my<0 or my>=self.MS: return MAX_DEPTH
            if self.world[my][mx]==1: return math.hypot(x-self.px,y-self.py)
        return MAX_DEPTH

    def throw_gren(self):
        if self.grenades<=0: return
        self.grenades-=1; cos,sin=math.cos(self.pa),math.sin(self.pa)
        self.glist.append({"x":self.px,"y":self.py,"vx":cos*0.15,"vy":sin*0.15,"t":90})

    def _explode(self,ex,ey):
        if len(self.snd)>2: self.snd[2].play()
        self.shake=12
        for e in self.enemies:
            if not e["alive"]: continue
            d=math.hypot(e["x"]-ex,e["y"]-ey)
            if d<4:
                dmg=int(150*(1-d/4)); e["hp"]-=dmg
                if e["hp"]<=0:
                    e["alive"]=False; e["dt"]=0; self.kills+=1; self.score+=ETYPES[e["type"]]["sc"]
        d=math.hypot(self.px-ex,self.py-ey)
        if d<4: self.hp-=int(30*(1-d/4)); self.dflash=40

    # ─── LEVELS ────────────────────────────────────────────
    def start_level(self,idx):
        self.reset(); self.state="PLAY"; self.clvl=idx; self.mode="level"
        lvl=LEVELS[idx]; self.twaves=lvl["waves"]
        self.world,self.MS=gen_level_map(idx)
        self.px=self.MS/2; self.py=self.MS/2; self.pa=0
        for i in range(idx+1):
            for wi in LEVELS[i].get("ul",[]):
                if wi not in self.warehouse:
                    self.warehouse.append(wi)
        selected=sorted(self.ws_selected) if self.ws_selected else [0]
        self.weapons=selected; self.cur_w=0
        self.ammo={}; self.reserve={}
        for wk in selected:
            self.ammo[wk]=WEAPONS[wk]["mag"]
            self.reserve[wk]=WEAPONS[wk]["mag"]*3

    def start_classic(self):
        self.reset(); self.state="PLAY"; self.mode="classic"
        self.world,self.MS=gen_classic_map()
        self.px=self.MS/2; self.py=self.MS/2; self.pa=0
        self.twaves=1; self.clvl=-1
        # Unlock all weapons to warehouse
        for i in range(5):
            if i not in self.warehouse:
                self.warehouse.append(i)
        selected=sorted(self.ws_selected) if self.ws_selected else [0]
        self.weapons=selected; self.cur_w=0
        self.ammo={}; self.reserve={}
        for wk in selected:
            self.ammo[wk]=WEAPONS[wk]["mag"]
            self.reserve[wk]=WEAPONS[wk]["mag"]*3

    def _spawn_wave(self):
        if self.mode=="level":
            base=LEVELS[self.clvl]["en"]; types=["basic","fast","shooter","heavy","boss"]
            scale=1+self.cwave*0.25
            counts=[int(base[0]*scale*0.6),int(base[1]*scale*0.5),int(base[2]*scale*0.5),
                    int(base[3]*scale*0.4),base[4] if self.cwave==self.twaves-1 else 0]
        else:
            types=["basic","fast","shooter","heavy","boss"]
            scale=1+self.cwave*0.3
            counts=[int(5*scale),int(2*scale),int(3*scale),int(1*scale),1 if self.cwave==self.twaves-1 else 0]

        cx,cy=self.MS//2,self.MS//2
        for ti,cnt in enumerate(counts):
            for _ in range(max(0,cnt)):
                for attempt in range(30):
                    sx=random.randint(2,self.MS-3); sy=random.randint(2,self.MS-3)
                    t=self.world[sy][sx]
                    if (t==0 or t>=2) and (abs(sx-cx)>5 or abs(sy-cy)>5):
                        et=ETYPES[types[ti]]
                        self.enemies.append({"x":sx+0.5,"y":sy+0.5,"hp":et["hp"],"max_hp":et["hp"],
                            "type":types[ti],"alive":True,"dt":0,"fc":et.get("fr",60)})
                        break
        self.cwave+=1

    # ─── DRAW ──────────────────────────────────────────────
    def draw(self):
        if self.state=="LOGIN": self._draw_login()
        elif self.state=="MENU": self._draw_menu()
        elif self.state=="SELECT": self._draw_select()
        elif self.state=="WAREHOUSE": self._draw_warehouse()
        elif self.state=="SHOP": self._draw_shop()
        elif self.state=="WEAPON_SELECT": self._draw_weapon_select()
        elif self.state=="PLAY": self._draw_game()
        elif self.state=="DEAD": self._draw_game(); self._draw_overlay(False)
        elif self.state=="WIN": self._draw_game(); self._draw_overlay(True)

    def _draw_login(self):
        self.screen.fill(BLACK)
        dtxt(self.screen,"WARFRONT 3D",(W//2,120),52,RED,True,True)
        dtxt(self.screen,"请输入你的名字:",(W//2,250),24,WHITE,ctr=True)
        bx,by,bw,bh=W//2-150,290,300,40
        pygame.draw.rect(self.screen,DGRAY,(bx,by,bw,bh),border_radius=5)
        pygame.draw.rect(self.screen,YELLOW,(bx,by,bw,bh),2,border_radius=5)
        dtxt(self.screen,self.name_buf+"|",(bx+10,by+8),22,WHITE,shd=False)
        dtxt(self.screen,"按 ENTER 确认",(W//2,360),18,GRAY,ctr=True)
        dtxt(self.screen,"提示: 中文输入法请按 Shift 切换英文模式或直接输入字母",(W//2,390),13,GRAY,ctr=True)

    def _draw_menu(self):
        horizon_y = 420
        # Draw real picture backgrounds
        if self.menu_sky:
            self.screen.blit(self.menu_sky, (0, 0))
        else:
            self.screen.fill(BLACK)
        if self.menu_ground:
            self.screen.blit(self.menu_ground, (0, horizon_y))
        if self.menu_ruins:
            ry = horizon_y - self.menu_ruins.get_height()
            self.screen.blit(self.menu_ruins, (0, max(0, ry)))

        # Dust particles (warm color)
        for p in self.cparts:
            a=p["a"]; c=(int(255*a),int(180*a),int(80*a))
            pygame.draw.circle(self.screen,c,(int(p["x"]),int(p["y"])),int(p["sz"]))
        pulse=math.sin(self.t*0.04)*0.12+0.88
        dtxt(self.screen,"WARFRONT 3D",(W//2,80),int(56*pulse),RED,True,True)
        dtxt(self.screen,f"欢迎, {self.user_name}",(W//2,140),22,YELLOW,ctr=True)
        dtxt(self.screen,"选择模式",(W//2,200),28,WHITE,True,True)
        pygame.draw.line(self.screen,(80,0,0),(0,170),(W,170),1)

        # Level challenge card
        bx,by=W//2-220,280
        hvr=bx<pygame.mouse.get_pos()[0]<bx+200 and by<pygame.mouse.get_pos()[1]<by+160
        pygame.draw.rect(self.screen,(50,50,60) if hvr else (35,35,42),(bx,by,200,160),border_radius=10)
        pygame.draw.rect(self.screen,YELLOW if hvr else GRAY,(bx,by,200,160),2,border_radius=10)
        dtxt(self.screen,"关卡挑战",(bx+100,by+50),24,WHITE,True,True)
        dtxt(self.screen,"9 个关卡",(bx+100,by+85),16,GRAY,ctr=True)
        dtxt(self.screen,"逐步解锁武器",(bx+100,by+110),14,DGREEN,ctr=True)

        # Classic mode card
        bx2=W//2+20
        hvr2=bx2<pygame.mouse.get_pos()[0]<bx2+200 and by<pygame.mouse.get_pos()[1]<by+160
        pygame.draw.rect(self.screen,(50,50,60) if hvr2 else (35,35,42),(bx2,by,200,160),border_radius=10)
        pygame.draw.rect(self.screen,YELLOW if hvr2 else GRAY,(bx2,by,200,160),2,border_radius=10)
        dtxt(self.screen,"经典模式",(bx2+100,by+50),24,WHITE,True,True)
        dtxt(self.screen,"开放地图探索",(bx2+100,by+85),16,GRAY,ctr=True)
        dtxt(self.screen,"100x100 大地图",(bx2+100,by+110),14,DGREEN,ctr=True)

        # My Warehouse button (under level challenge)
        wx,wy=bx,by+180
        hvr_w=wx<pygame.mouse.get_pos()[0]<wx+200 and wy<pygame.mouse.get_pos()[1]<wy+60
        pygame.draw.rect(self.screen,(50,50,60) if hvr_w else (35,35,42),(wx,wy,200,60),border_radius=10)
        pygame.draw.rect(self.screen,YELLOW if hvr_w else GRAY,(wx,wy,200,60),2,border_radius=10)
        dtxt(self.screen,"我的仓库",(wx+100,wy+30),22,WHITE,True,True)

        # Shop button (under classic mode)
        sx,sy=bx2,by+180
        hvr_s=sx<pygame.mouse.get_pos()[0]<sx+200 and sy<pygame.mouse.get_pos()[1]<sy+60
        pygame.draw.rect(self.screen,(50,50,60) if hvr_s else (35,35,42),(sx,sy,200,60),border_radius=10)
        pygame.draw.rect(self.screen,YELLOW if hvr_s else GRAY,(sx,sy,200,60),2,border_radius=10)
        dtxt(self.screen,"商店",(sx+100,sy+30),22,WHITE,True,True)
        dtxt(self.screen,"出售子弹、手榴弹",(sx+100,sy+48),11,GRAY,ctr=True)

        dtxt(self.screen,"按 1 关卡挑战 | 按 2 经典模式 | ESC 退出",(W//2,H-50),14,GRAY,ctr=True)

        # Exit login button (bottom-right corner)
        ex_x, ex_y = W-130, H-80
        mx, my = pygame.mouse.get_pos()
        hvr_ex = ex_x < mx < ex_x+120 and ex_y < my < ex_y+35
        pygame.draw.rect(self.screen, (60,40,40) if hvr_ex else (40,25,25), (ex_x, ex_y, 120, 35), border_radius=6)
        pygame.draw.rect(self.screen, RED if hvr_ex else GRAY, (ex_x, ex_y, 120, 35), 2, border_radius=6)
        dtxt(self.screen, "退出登录", (ex_x+60, ex_y+17), 16, WHITE, True, True)

        # Bottom bar
        for i in range(30):
            y=H-30+i; r=i/30
            c=(int(YELLOW[0]*(1-r*0.7)),int(YELLOW[1]*(1-r*0.7)),int(YELLOW[2]*(1-r*0.7)))
            pygame.draw.line(self.screen,c,(0,y),(W,y))
        for x in range(-30,W+30,50):
            pygame.draw.polygon(self.screen,BLACK,[(x,H-30),(x+25,H-30),(x+40,H),(x+15,H)])

    def _draw_select(self):
        self.screen.fill((18,18,22))
        for x in range(0,W,40): pygame.draw.line(self.screen,(25,25,30),(x,0),(x,H))
        for y in range(0,H,40): pygame.draw.line(self.screen,(25,25,30),(0,y),(W,y))
        dtxt(self.screen,"选择关卡",(W//2,50),38,WHITE,True,True)
        pygame.draw.line(self.screen,YELLOW,(W//2-180,85),(W//2+180,85),2)

        gx0=W//2-340; gy0=110
        for i in range(9):
            c,r=i%3,i//3; rx,ry=gx0+c*240,gy0+r*140
            rw,rh=215,115; ul=i<=self.max_ul
            mx,my=pygame.mouse.get_pos()
            hvr=rx<mx<rx+rw and ry<my<ry+rh and ul
            bg=(55,55,65) if hvr else (40,40,48) if ul else (25,25,28)
            bdr=YELLOW if hvr else GRAY if ul else (50,50,55)
            pygame.draw.rect(self.screen,bg,(rx,ry,rw,rh),border_radius=8)
            pygame.draw.rect(self.screen,bdr,(rx,ry,rw,rh),2 if hvr else 1,border_radius=8)
            if ul:
                pygame.draw.circle(self.screen,YELLOW if hvr else (180,160,50),(rx+22,ry+22),14)
                dtxt(self.screen,str(i+1),(rx+22,ry+22),16,BLACK,True,True,False)
                dtxt(self.screen,LEVELS[i]["name"],(rx+45,ry+14),20,WHITE,True)
                diff=min(5,i//2+1)
                dtxt(self.screen,"★"*diff+"☆"*(5-diff),(rx+12,ry+45),14,YELLOW,shd=False)
                dtxt(self.screen,f"{LEVELS[i]['waves']} waves",(rx+12,ry+68),12,GRAY,shd=False)
                if LEVELS[i].get("ul"):
                    wn=", ".join(WEAPONS[w]["name"] for w in LEVELS[i]["ul"])
                    dtxt(self.screen,f"解锁: {wn}",(rx+12,ry+88),11,DGREEN,shd=False)
            else:
                dtxt(self.screen,"LOCKED",(rx+rw//2,ry+rh//2),18,(60,60,65),True,True,False)

        for i in range(35):
            y=H-35+i; r=i/35
            c=(int(YELLOW[0]*(1-r*0.7)),int(YELLOW[1]*(1-r*0.7)),int(YELLOW[2]*(1-r*0.7)))
            pygame.draw.line(self.screen,c,(0,y),(W,y))
        for x in range(-35,W+35,50):
            pygame.draw.polygon(self.screen,BLACK,[(x,H-35),(x+25,H-35),(x+40,H),(x+15,H)])
        dtxt(self.screen,"ESC 返回 | 点击关卡开始",(W//2,H-22),15,BLACK,True,True,False)

    # ─── 3D GAME RENDER ───────────────────────────────────
    def _draw_game(self):
        buf=self.buf
        th=LEVELS[self.clvl]["th"] if self.clvl>=0 else (70,85,55)

        # Third person camera offset (further back, like image 2)
        if self.tp:
            vpx=self.px-math.cos(self.pa)*5.5
            vpy=self.py-math.sin(self.pa)*5.5
        else:
            vpx,vpy=self.px,self.py

        sx=int(random.uniform(-self.shake,self.shake)) if self.shake>0 else 0
        sy=int(random.uniform(-self.shake,self.shake)) if self.shake>0 else 0

        # ── PUBG-style jump camera (scene + walls shift together) ──
        if not self.tp:
            jump_off = int(self.jump_y * 3)
        else:
            jump_off = 0

        # Sky & floor (shifted with jump in first person)
        buf.fill((th[0]//4,th[1]//4,th[2]//4),(0,0,BW,BH//2 + jump_off))
        buf.fill((th[0]//2,th[1]//2,th[2]//2),(0,BH//2 + jump_off,BW,BH//2 - jump_off))

        # Cast rays
        rays,zbuf=cast_rays(vpx,vpy,self.pa,self.world,self.MS)
        sw=BW//NUM_RAYS

        # Fog parameters
        fog_start=MAX_DEPTH*0.5; fog_end=MAX_DEPTH*0.9
        fog_col=(th[0]//4,th[1]//4,th[2]//4)

        for i,(dist,side,mx,my) in enumerate(rays):
            wh=min(BH,int(BH/max(dist,0.1)))
            top=(BH-wh)//2+jump_off
            shade=(1.0 if side==0 else 0.7)*max(0.2,1-dist/MAX_DEPTH)
            wc=(int(th[0]*shade),int(th[1]*shade),int(th[2]*shade))
            # Fog blend
            if dist>fog_start:
                fog=min(1,(dist-fog_start)/(fog_end-fog_start))
                wc=tuple(int(wc[j]*(1-fog)+fog_col[j]*fog) for j in range(3))
            pygame.draw.rect(buf,wc,(i*sw+sx//2,top+sy//2,sw+1,wh))

        # Entities (enemies + player sprite in 3rd person + grenades)
        ents=[]
        for e in self.enemies:
            d=math.hypot(e["x"]-vpx,e["y"]-vpy)
            ents.append((d,e,"enemy"))
        if self.tp:
            ents.append((math.hypot(self.px-vpx,self.py-vpy),{"x":self.px,"y":self.py},"player"))
        for g in self.glist:
            d=math.hypot(g["x"]-vpx,g["y"]-vpy)
            ents.append((d,g,"grenade"))
        ents.sort(key=lambda x:-x[0])

        for dist,obj,otyp in ents:
            if dist<0.3: continue
            dx=obj["x"]-vpx; dy=obj["y"]-vpy
            angle=math.atan2(dy,dx)-self.pa
            angle=((angle+math.pi)%(2*math.pi))-math.pi
            if abs(angle)>FOV/2+0.3: continue
            scr_x=int((0.5+angle/FOV)*BW)
            ri=min(NUM_RAYS-1,max(0,scr_x//sw))
            if ri<len(zbuf) and dist>zbuf[ri]+0.5: continue

            fog_f=min(1,max(0,(dist-fog_start)/(fog_end-fog_start)))
            shade=max(0.3,1-dist/MAX_DEPTH)*(1-fog_f*0.8)

            if otyp=="enemy":
                et=ETYPES[obj["type"]]
                sprh=int((BH/max(dist,0.1))*et["sz"])
                sprw=max(2,int(sprh*0.5))
                top=(BH-sprh)//2+jump_off
                draw_soldier(buf,scr_x+sx//2,top+sy//2,sprw,sprh,et["col"],obj["alive"],obj["type"],shade)
                if obj["alive"] and obj["hp"]<obj["max_hp"]:
                    bw=sprw; bh=max(2,sprh//20); by=top-bh-2
                    pygame.draw.rect(buf,VGRAY,(scr_x-bw//2+sx//2,by+sy//2,bw,bh))
                    pygame.draw.rect(buf,RED,(scr_x-bw//2+sx//2,by+sy//2,int(bw*obj["hp"]/obj["max_hp"]),bh))
            elif otyp=="player":
                # Third person: player sprite actually jumps up, scene stays still
                pjump=int(self.jump_y*4)
                sprh=int((BH/max(dist,0.1))*0.6)
                sprw=max(2,int(sprh*0.4))
                top=(BH-sprh)//2-pjump
                draw_soldier(buf,scr_x+sx//2,top+sy//2,sprw,sprh,(60,100,60),True,"basic",shade)
            elif otyp=="grenade":
                sz=max(2,int(8/dist))
                gc=RED if obj["t"]<30 and obj["t"]%6<3 else (70,90,50)
                pygame.draw.circle(buf,gc,(scr_x+sx//2,BH//2+sy//2+jump_off),sz)

        # Scale to screen
        scaled=pygame.transform.scale(buf,(W,H))
        self.screen.blit(scaled,(0,0))

        # Damage flash
        if self.dflash>0:
            fl=pygame.Surface((W,H),pygame.SRCALPHA); fl.fill((255,0,0,min(100,self.dflash)))
            self.screen.blit(fl,(0,0))

        # Muzzle flash
        if self.muzzle>0:
            fx=W//2+random.randint(-10,10); fy=H-180+random.randint(-5,5)
            pygame.draw.circle(self.screen,(255,220,80),(fx,fy),20+self.muzzle*4)
            pygame.draw.circle(self.screen,(255,255,200),(fx,fy),10+self.muzzle*2)

        # Weapon view (only in first person) — with jump bob
        if not self.tp: self._draw_weapon()

        # Crosshair
        cx2,cy2=W//2,H//2
        for dx,dy,l in [(-12,0,8),(4,0,8),(0,-12,8),(0,4,8)]:
            pygame.draw.line(self.screen,WHITE,(cx2+dx,cy2+dy),(cx2+dx+(l if dx else 0),cy2+dy+(l if dy else 0)),2)

        # Floats
        for f in self.floats:
            dx=f["x"]-vpx; dy=f["y"]-vpy
            angle=math.atan2(dy,dx)-self.pa
            angle=((angle+math.pi)%(2*math.pi))-math.pi
            if abs(angle)>FOV/2: continue
            fsx=int((0.5+angle/FOV)*W); alpha=f["t"]/40
            c=tuple(int(v*alpha) for v in f["col"])
            dtxt(self.screen,f["txt"],(fsx,H//2-20-f["t"]+jump_off),18,c,True,True)

        # HUD
        self._draw_hud()

        # Minimap
        self._draw_minimap()

        # Wave announcement
        if self.wdly>60:
            dtxt(self.screen,f"- WAVE {self.cwave+1} -",(W//2,H//2-30),40,RED,True,True)

    def _draw_weapon(self):
        wk=self.weapons[self.cur_w]; wc=WCOL[wk]
        # First person jump bob: weapon moves down when player jumps up
        jump_bob=int(self.jump_y*4)
        bx=W//2+80; by=H-50+int(self.recoil*5)-jump_bob
        shapes=[
            [(bx-15,by-60,30,50),(bx-10,by-20,20,35)],
            [(bx-12,by-100,24,80),(bx-8,by-25,16,40),(bx-6,by-110,12,15)],
            [(bx-14,by-110,28,90),(bx-10,by-25,20,40)],
            [(bx-10,by-80,20,60),(bx-8,by-25,16,40),(bx-5,by-15,10,25)],
            [(bx-10,by-120,20,100),(bx-8,by-25,16,40)],
        ]
        for rect in shapes[wk]:
            pygame.draw.rect(self.screen,wc if rect==shapes[wk][0] else DGRAY,rect)

    def _draw_hud(self):
        hh=60; hy=H-hh
        for i in range(hh):
            r=i/hh; c=(int(YELLOW[0]*r*0.3),int(YELLOW[1]*r*0.3),int(YELLOW[2]*r*0.3))
            pygame.draw.line(self.screen,c,(0,hy+i),(W,hy+i))
        pygame.draw.line(self.screen,YELLOW,(0,hy),(W,hy),2)

        dtxt(self.screen,"HP",(12,hy+8),13,YELLOW,True,shd=False)
        dbar(self.screen,35,hy+8,150,14,self.hp/self.max_hp,GREEN if self.hp>30 else RED)
        dtxt(self.screen,f"{int(self.hp)}",(45,hy+9),11,WHITE,shd=False)

        wk=self.weapons[self.cur_w]; w=WEAPONS[wk]
        at=f"换弹..." if self.rld>0 else f"{self.ammo[wk]}/{self.reserve[wk]}"
        dtxt(self.screen,w["name"],(W//2-55,hy+5),15,WCOL[wk],True)
        dtxt(self.screen,at,(W//2-55,hy+24),18,YELLOW,True)

        for i in range(len(self.weapons)):
            sx2=W//2-55+i*40; c=YELLOW if i==self.cur_w else DGRAY
            pygame.draw.rect(self.screen,c,(sx2,hy+46,36,10),1)
            dtxt(self.screen,f"{i+1}",(sx2+3,hy+45),8,c,shd=False)

        dtxt(self.screen,"手榴弹",(W-170,hy+8),13,YELLOW,True,shd=False)
        for i in range(5):
            gx=W-170+i*18
            pygame.draw.circle(self.screen,(70,90,50) if i<self.grenades else DGRAY,(gx+7,hy+33),6,0 if i<self.grenades else 1)

        mode_txt="关卡" if self.mode=="level" else "经典"
        dtxt(self.screen,f"{mode_txt} | V 视角 | M 地图",(10,H-hh-20),12,GRAY,shd=False)

        if self.mode=="level":
            dtxt(self.screen,LEVELS[self.clvl]["name"],(10,6),16,WHITE,True)
        alive=sum(1 for e in self.enemies if e["alive"])
        dtxt(self.screen,f"Wave {self.cwave+1}/{self.twaves} | 敌人:{alive}",(10,26),13,GRAY)
        dtxt(self.screen,f"得分:{self.score} 击杀:{self.kills}",(10,42),13,YELLOW,shd=False)
        dtxt(self.screen,self.user_name,(10,58),12,GRAY,shd=False)
        dtxt(self.screen,f"金币:{self.coins}",(W-100,6),13,YELLOW,shd=False)

    def _draw_minimap(self):
        if not self.world: return
        if self.minimap_big:
            ms=12; ox=W//2; oy=0; mw=self.MS*ms; mh=self.MS*ms
            # Background
            pygame.draw.rect(self.screen,(0,0,0,180),(ox,oy,mw,mh))
        else:
            ms=2; ox=W-160; oy=10; mw=self.MS*ms; mh=self.MS*ms
            pygame.draw.rect(self.screen,(0,0,0,160),(ox-2,oy-2,mw+4,mh+4))

        # Only draw visible portion for large maps
        view_px=self.px; view_py=self.py
        r=50 if self.minimap_big else 25
        for y in range(max(0,int(view_py-r)),min(self.MS,int(view_py+r))):
            for x in range(max(0,int(view_px-r)),min(self.MS,int(view_px+r))):
                t=self.world[y][x]
                if t==1: c=GRAY
                elif t>=2: c=DGREEN
                else: c=(20,20,25)
                rx=ox+(x-(view_px-r if self.minimap_big else 0))*ms
                ry=oy+(y-(view_py-r if self.minimap_big else 0))*ms
                if self.minimap_big:
                    rx=ox+x*ms; ry=oy+y*ms
                pygame.draw.rect(self.screen,c,(rx,ry,ms,ms))

        # Player dot
        if self.minimap_big:
            ppx=ox+int(self.px*ms); ppy=oy+int(self.py*ms)
        else:
            ppx=ox+int(self.px*ms); ppy=oy+int(self.py*ms)
        pygame.draw.circle(self.screen,YELLOW,(ppx,ppy),max(2,ms*2))
        # Direction line
        dl=max(5,ms*4)
        pygame.draw.line(self.screen,YELLOW,(ppx,ppy),
            (ppx+int(math.cos(self.pa)*dl),ppy+int(math.sin(self.pa)*dl)),2)

        # Enemy dots
        for e in self.enemies:
            if not e["alive"]: continue
            if self.minimap_big:
                ex=ox+int(e["x"]*ms); ey=oy+int(e["y"]*ms)
            else:
                ex=ox+int(e["x"]*ms); ey=oy+int(e["y"]*ms)
            if ox<ex<ox+mw and oy<ey<oy+mh:
                pygame.draw.circle(self.screen,RED,(ex,ey),max(1,ms))

        if self.minimap_big:
            dtxt(self.screen,"按 M 关闭",(ox+mw//2,oy+mh+10),14,WHITE,True,True)

    def _draw_overlay(self,won):
        ov=pygame.Surface((W,H),pygame.SRCALPHA); ov.fill((0,0,0,160)); self.screen.blit(ov,(0,0))
        if won:
            dtxt(self.screen,"MISSION COMPLETE",(W//2,H//2-60),48,YELLOW,True,True)
            dtxt(self.screen,"任 务 完 成",(W//2,H//2-10),28,(200,200,100),ctr=True)
            if self.mode=="level" and LEVELS[self.clvl].get("ul"):
                wn=", ".join(WEAPONS[w]["name"] for w in LEVELS[self.clvl]["ul"])
                dtxt(self.screen,f"解锁: {wn}!",(W//2,H//2+60),18,DGREEN,True,True)
        else:
            dtxt(self.screen,"MISSION FAILED",(W//2,H//2-60),48,RED,True,True)
            dtxt(self.screen,"任 务 失 败",(W//2,H//2-10),28,(200,100,100),ctr=True)
        dtxt(self.screen,f"得分:{self.score} | 击杀:{self.kills}",(W//2,H//2+25),20,WHITE,ctr=True)
        if self.t%80<55:
            dtxt(self.screen,"ENTER 继续 | ESC 返回",(W//2,H//2+75),20,YELLOW,ctr=True)
        keys=pygame.key.get_pressed()
        if keys[pygame.K_RETURN] or keys[pygame.K_SPACE]:
            pygame.time.wait(200)
            self.state="MENU" if self.mode=="classic" else "SELECT"
        elif keys[pygame.K_ESCAPE]:
            pygame.time.wait(200); self.state="MENU"

# ═══════════════════════════════════════════════════════════════
if __name__=="__main__":
    Game().run()
