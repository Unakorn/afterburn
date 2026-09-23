"""GPU visuals: six procedural worlds, floating-point trails and bloom."""
from __future__ import annotations

import math
import os
from pathlib import Path

import moderngl
import numpy as np
from PIL import Image, ImageDraw, ImageFont

VERTEX = '''#version 330
out vec2 v_uv;
void main() {
    vec2 p=vec2(float((gl_VertexID<<1)&2),float(gl_VertexID&2));
    v_uv=p; gl_Position=vec4(p*2.-1.,0,1);
}'''
TRAIL = '''#version 330
in vec2 v_uv; out vec4 fragColor;
uniform sampler2D currentFrame, history;
uniform float amount, spin;
void main() {
    vec2 q=v_uv-.5;
    float c=cos(spin), s=sin(spin);
    q=mat2(c,-s,s,c)*q*.998+.5;
    vec3 cur=texture(currentFrame,v_uv).rgb;
    vec3 old=texture(history,q).rgb;
    fragColor=vec4(mix(cur,max(cur,old*.945),amount),1);
}'''
BLUR = '''#version 330
in vec2 v_uv; out vec4 fragColor;
uniform sampler2D source;
uniform vec2 direction;
uniform float threshold;
vec3 tap(vec2 uv) {
    vec3 c=texture(source,uv).rgb;
    return c*max(0.,max(c.r,max(c.g,c.b))-threshold)/(max(c.r,max(c.g,c.b))+.001);
}
void main() {
    vec3 c=tap(v_uv)*.227027;
    c+=tap(v_uv+direction*1.384615)*.316216;
    c+=tap(v_uv-direction*1.384615)*.316216;
    c+=tap(v_uv+direction*3.230769)*.070270;
    c+=tap(v_uv-direction*3.230769)*.070270;
    fragColor=vec4(c,1);
}'''
COMPOSITE = '''#version 330
in vec2 v_uv; out vec4 fragColor;
uniform sampler2D source, bloom, title;
uniform float beat, treble, energy, time, calm, titleAlpha;
vec3 aces(vec3 x) { return clamp((x*(2.51*x+.03))/(x*(2.43*x+.59)+.14),0.,1.); }
float hash(vec2 p) { return fract(sin(dot(p,vec2(12.9898,78.233)))*43758.5453); }
void main() {
    vec2 uv=v_uv;
    float intensity=mix(1.,.20,calm);
    float line=floor(uv.y*180.);
    float tear=step(.983,hash(vec2(line,floor(time*9.))))*beat*treble;
    uv.x+=(hash(vec2(line,7.))-.5)*.016*tear*intensity;
    vec2 ca=(uv-.5)*(.0015+beat*.0045)*intensity;
    vec3 c=vec3(texture(source,uv+ca).r,texture(source,uv).g,texture(source,uv-ca).b);
    c+=texture(bloom,uv).rgb*(.66+.34*energy);
    c*=1.+beat*.13*intensity;
    float vignette=1.-.25*pow(length((v_uv-.5)*1.4),1.4);
    c=pow(aces(c*.98*vignette),vec3(1./2.2));
    c+=(hash(gl_FragCoord.xy+fract(time)*239.)-.5)*.011;
    vec4 txt=texture(title,v_uv);
    c=mix(c,txt.rgb,txt.a*titleAlpha);
    fragColor=vec4(clamp(c,0.,1.),1);
}'''

SCENE_NAMES = ('Prismatic core', 'Hyperspace', 'Kaleidoscope', 'Nebula', 'Vortex', 'Neon terrain')


def _font(size: int, bold: bool = False):
    fonts = Path(os.environ.get('WINDIR', 'C:/Windows')) / 'Fonts'
    for filename in (('bahnschrift.ttf', 'segoeuib.ttf', 'arialbd.ttf') if bold else ('segoeui.ttf', 'arial.ttf')):
        try:
            return ImageFont.truetype(str(fonts / filename), size)
        except OSError:
            pass
    return ImageFont.load_default(size=size)


def make_title(width: int, height: int, text: str) -> Image.Image:
    canvas = Image.new('RGBA', (width, height))
    draw = ImageDraw.Draw(canvas)
    short = min(width, height)
    # A quiet title card appears over the opening few seconds only.
    size = max(14, int(short * .055))
    margin = int(width * .10)
    words = text.replace('_', ' ').strip().split()
    lines: list[str] = []
    font = _font(size, True)
    line = ''
    for word in words:
        proposed = (line + ' ' + word).strip()
        if draw.textlength(proposed, font=font) > width - margin * 2 and line:
            lines.append(line)
            line = word
        else:
            line = proposed
    if line:
        lines.append(line)
    lines = lines[:3] or ['UNTITLED']
    while max(draw.textlength(s, font=font) for s in lines) > width-margin*2 and size > 10:
        size -= 1
        font = _font(size, True)
    y = int(height * .77)
    # Soft local shade makes the title readable over every palette.
    for dy in range(-int(short*.04), int(short*.21)):
        opacity = int(105 * math.exp(-((dy-short*.06)/(short*.12))**2))
        draw.line((0, y+dy, width, y+dy), fill=(0, 0, 0, opacity))
    draw.line((margin, y-int(short*.024), margin+int(short*.075), y-int(short*.024)), fill=(153, 240, 255, 230), width=max(1,short//400))
    for line in lines:
        draw.text((margin,y),line,font=font,fill=(245,247,255,245),stroke_width=0)
        y += int(size*1.25)
    return canvas.transpose(Image.Transpose.FLIP_TOP_BOTTOM)


class Director:
    """Choose scenes on detected hits, with 8–16 second breathing room."""
    def __init__(self, features: np.ndarray, fps: int, seed: int, scene_seconds: float = 12):
        rng = np.random.default_rng(seed)
        order = [0, 1, 2, 3, 4, 5]
        tail = list(rng.permutation([1, 2, 3, 4, 5]))
        order = [0] + tail
        self.events = [(0, order[0])]
        n = len(features)
        cursor = 0
        count = 1
        while True:
            target = cursor + int(fps * scene_seconds * rng.uniform(.82, 1.22))
            if target >= n:
                break
            lo, hi = max(cursor+fps*3,target-fps), min(n,target+fps*2)
            score = features[lo:hi,4] + features[lo:hi,6]*.5
            if len(score) and float(score.max()) > .18:
                target = lo+int(score.argmax())
            self.events.append((target, order[count % 6]))
            cursor = target
            count += 1
            if count % 6 == 0:
                last = order[-1]
                order = list(rng.permutation(6))
                if order[0] == last:
                    order[0], order[1] = order[1], order[0]
        self.index = 0
        self.fps = fps

    def at(self, frame: int) -> tuple[int, int, float]:
        while self.index+1 < len(self.events) and frame >= self.events[self.index+1][0]:
            self.index += 1
        start, current = self.events[self.index]
        previous = self.events[max(0,self.index-1)][1]
        mix = 1. if self.index == 0 else min(1., (frame-start)/(self.fps*.85))
        return current, previous, mix


class Renderer:
    def __init__(self, width: int, height: int, fps: int, seed: int, title: str = '', calm: bool = False):
        self.ctx = None
        self.resources = []
        try:
            self._initialize(width,height,fps,seed,title,calm)
        except BaseException:
            self.close()
            raise

    def _initialize(self, width: int, height: int, fps: int, seed: int, title: str, calm: bool):
        try:
            self.ctx = moderngl.create_standalone_context(require=330)
        except Exception as exc:
            raise RuntimeError('The GPU renderer needs OpenGL 3.3. Update your NVIDIA/AMD/Intel graphics driver and run locally (some remote desktops hide the GPU).') from exc
        self.width, self.height, self.fps = width,height,fps
        self.calm = float(calm)
        self.motion = 0.
        self.seed = (seed % 100000)/1000.
        self.resources = []
        self.info = self.ctx.info.get('GL_RENDERER','OpenGL GPU')
        shaders = Path(__file__).parent/'shaders'
        scene_code = '\n'.join((shaders/name).read_text(encoding='utf-8') for name in ('common.glsl','kinetic.glsl','worlds.glsl','scene_main.glsl'))
        self.scene = self._program(scene_code)
        self.trail = self._program(TRAIL)
        self.blur = self._program(BLUR)
        self.composite = self._program(COMPOSITE)
        self.raw, self.raw_fb = self._target((width,height))
        self.history = [self._target((width,height)) for _ in range(2)]
        self.small_size = (max(1,width//2),max(1,height//2))
        self.bloom = [self._target(self.small_size) for _ in range(2)]
        self.output,self.output_fb = self._target((width,height),dtype='f1',components=3)
        self.spectrum = self.ctx.texture((32,1),1,dtype='f4')
        self.spectrum.filter = (moderngl.LINEAR, moderngl.LINEAR)
        self.spectrum.repeat_x = False
        self.resources.append(self.spectrum)
        title_image = make_title(width,height,title) if title else Image.new('RGBA',(1,1))
        self.title = self.ctx.texture(title_image.size,4,title_image.tobytes())
        self.title.filter = (moderngl.LINEAR,moderngl.LINEAR)
        self.resources.append(self.title)
        self.has_title = bool(title)
        self.ping = 0
        self._set(self.scene, u_resolution=(float(width),float(height)),u_seed=self.seed,u_spectrum=0)
        self._set(self.trail,currentFrame=0,history=1)
        self._set(self.blur,source=0)
        self._set(self.composite,source=0,bloom=1,title=2,calm=self.calm)

    def _program(self, fragment):
        program = self.ctx.program(vertex_shader=VERTEX,fragment_shader=fragment)
        vao = self.ctx.vertex_array(program,[])
        self.resources.extend([program,vao])
        return program,vao

    def _target(self,size,dtype='f2',components=3):
        texture = self.ctx.texture(size,components,dtype=dtype)
        texture.filter = (moderngl.LINEAR,moderngl.LINEAR)
        texture.repeat_x = texture.repeat_y = False
        fb = self.ctx.framebuffer([texture])
        fb.clear(0,0,0,1)
        self.resources.extend([texture,fb])
        return texture,fb

    @staticmethod
    def _set(bundle,**uniforms):
        for name,value in uniforms.items():
            if name in bundle[0]:
                bundle[0][name].value=value

    @staticmethod
    def _draw(bundle,fb):
        fb.use()
        bundle[1].render(mode=moderngl.TRIANGLES,vertices=3)

    def render(self, frame: int, audio: np.ndarray, spectrum: np.ndarray, scene: tuple[int,int,float]) -> bytes:
        t=frame/self.fps
        self.motion+=(.55+float(audio[0])*.95+float(audio[3])*.42)/self.fps
        self.spectrum.write(np.asarray(spectrum,dtype='f4').tobytes())
        self.spectrum.use(0)
        self._set(self.scene,u_time=t,u_motion=self.motion,u_audio=tuple(float(x) for x in audio[:4]),u_pulse=(float(audio[4]),float(audio[5]),float(audio[6]),self.calm),u_scene=scene[0],u_previous=scene[1],u_transition=scene[2])
        self._draw(self.scene,self.raw_fb)
        self.raw.use(0)
        self.history[1-self.ping][0].use(1)
        self._set(self.trail,amount=.40 if self.calm else .68,spin=.0004*math.sin(t*.3))
        self._draw(self.trail,self.history[self.ping][1])
        current=self.history[self.ping][0]
        current.use(0)
        self._set(self.blur,direction=(1./self.small_size[0],0.),threshold=.55)
        self._draw(self.blur,self.bloom[0][1])
        for i in range(5):
            source=i%2
            dest=1-source
            self.bloom[source][0].use(0)
            direction=(0.,(1.+i*.5)/self.small_size[1]) if i%2==0 else ((1.+i*.5)/self.small_size[0],0.)
            self._set(self.blur,direction=direction,threshold=0.)
            self._draw(self.blur,self.bloom[dest][1])
        current.use(0)
        self.bloom[1][0].use(1)
        self.title.use(2)
        title_alpha=min(1.,max(0.,(t-.4)/.8))*min(1.,max(0.,(6.-t)/1.2)) if self.has_title else 0.
        self._set(self.composite,beat=float(audio[4]),treble=float(audio[2]),energy=float(audio[3]),time=t,titleAlpha=title_alpha)
        self._draw(self.composite,self.output_fb)
        self.ping=1-self.ping
        return self.output_fb.read(components=3,alignment=1)

    def close(self):
        for resource in reversed(self.resources):
            try:
                resource.release()
            except Exception:
                pass
        self.resources.clear()
        if self.ctx is not None:
            self.ctx.release()
            self.ctx = None
