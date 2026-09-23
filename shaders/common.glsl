#version 330
in vec2 v_uv;
out vec4 fragColor;
uniform vec2 u_resolution;
uniform float u_time;
uniform float u_motion;
uniform float u_seed;
uniform vec4 u_audio;
uniform vec4 u_pulse;
uniform sampler2D u_spectrum;
uniform int u_scene;
uniform int u_previous;
uniform float u_transition;
const float PI = 3.14159265359;
const float TAU = 6.28318530718;
mat2 rot(float a) { float c=cos(a), s=sin(a); return mat2(c,-s,s,c); }
float hash21(vec2 p) { p=fract(p*vec2(123.34,456.21)); p+=dot(p,p+45.32); return fract(p.x*p.y); }
float noise2(vec2 p) {
    vec2 i=floor(p),f=fract(p); f=f*f*(3.-2.*f);
    return mix(mix(hash21(i),hash21(i+vec2(1,0)),f.x),mix(hash21(i+vec2(0,1)),hash21(i+1.),f.x),f.y);
}
vec3 palette(float t) {
    return .54+.46*cos(TAU*(vec3(1.,1.,1.)*(t+u_seed*.013)+vec3(.03,.36,.63)));
}
float spec(float x) { return texture(u_spectrum,vec2(clamp(x,.015625,.984375),.5)).r; }
float lineGlow(float d,float w) { return pow(w/max(abs(d),w*.4),1.32); }
float ribbon(float d,float w) { return exp(-abs(d)/w); }
