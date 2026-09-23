// A continuous flight through a spectral polygon tunnel.
vec3 sceneTunnel(vec2 p) {
    float t=u_motion, bass=u_audio.x, beat=u_pulse.x;
    p=rot(.12*sin(t*.2)+.09*beat)*p;
    p+=vec2(.12*sin(t*.31),.10*cos(t*.23));
    p/=1.+.09*bass;
    float r=max(length(p),.025), a=atan(p.y,p.x);
    float poly=r*(.91+.09*cos(a*6.+t*.12));
    float z=1.7/max(poly,.035);
    float twist=a+.12*z+.19*sin(z*.33-t*.18);
    float sector=twist/TAU*12.;
    float wire=abs(fract(sector)-.5)*r;
    float ring=abs(fract(z-t*1.3)-.5)*r*r*.30;
    float env=.35+.65*spec(fract(abs(a)/PI));
    vec3 col=palette(z*.055+t*.025)*lineGlow(wire,.0017+.0014*bass)*env;
    col+=palette(z*.026+.47)*lineGlow(ring,.0025)*(.5+.6*bass);
    float dash=step(.78,fract(z*2.-t*2.6));
    col+=palette(.65+a*.12)*lineGlow(wire,.007)*dash*.21;
    float fog=exp(-z*.029)*smoothstep(.055,.3,r);
    col*=fog;
    col+=vec3(.02,.035,.11)*exp(-r*1.7);
    col+=palette(.7)*exp(-r*12.)*(.5+beat);
    // Sparse passing stardust, independently distributed in depth.
    vec2 starUV=vec2(twist*10.,z-t*1.3);
    vec2 cell=floor(starUV); vec2 f=fract(starUV)-.5;
    float h=hash21(cell+u_seed);
    col+=palette(h)*exp(-length(f*vec2(1.,.7))*90.)*step(.70,h)*3.*fog;
    return min(col,vec3(14));
}

// Twisting electric filaments trace a three-dimensional torus knot.
vec3 sceneVortex(vec2 p) {
    float t=u_motion*.25;
    p=rot(.13*sin(t))*p;
    vec3 col=vec3(.006,.009,.027);
    float r=length(p), angle=atan(p.y,p.x);
    col+=palette(.43)*exp(-r*r*2.)*.065;
    for(int i=0;i<28;i++) {
        float fi=float(i), phase=fi/28.*TAU;
        vec2 q=rot(t*.4+phase*.1)*p;
        float a=atan(q.y,q.x);
        float wave=.63+.19*cos(a*3.+t+phase)+.11*sin(a*2.-t*.7+phase*1.7);
        wave+=.11*u_audio.x+.035*spec(fract(a/TAU+phase/TAU));
        float d=abs(length(q)-wave);
        float depth=.45+.55*sin(a*2.+phase+t);
        float w=.0015+.0012*depth;
        vec3 c=palette(phase/TAU*.65+a*.03+t*.035);
        col+=c*lineGlow(d,w)*(.06+.045*depth);
    }
    for(int i=0;i<10;i++) {
        float h=float(i)*.618;
        float rr=fract(h+u_motion*.045);
        float a=h*13.+u_motion*.09;
        vec2 pos=vec2(cos(a),sin(a))*rr*1.4;
        col+=palette(h)*exp(-length(p-pos)*180.)*(1.+u_audio.z)*.8;
    }
    float ring=abs(r-(.34+.035*sin(angle*7.+t*2.)+.055*u_pulse.x));
    col+=palette(.85)*lineGlow(ring,.0018)*.28;
    return min(col,vec3(14));
}

// Endless rippling wire terrain, rendered as thin luminous contours.
vec3 sceneTerrain(vec2 p) {
    float t=u_motion*.6;
    vec3 ro=vec3(.7*sin(t*.10),1.7,-t*2.);
    vec3 rd=normalize(vec3(p.x,p.y-.18,1.5));
    rd.yz=rot(-.22)*rd.yz;
    vec3 col=vec3(.009,.012,.035);
    float travel=.1;
    for(int i=0;i<60;i++) {
        vec3 q=ro+rd*travel;
        float h=.22*sin(q.x*1.4+q.z*.6)+.30*sin(q.z*.43-q.x*.7);
        h+=u_audio.x*.4*sin(q.x*2.+q.z*.9);
        float d=q.y-h;
        if(abs(d)<.014 || travel>24.) break;
        travel+=max(abs(d)*.42,.022);
    }
    vec3 pos=ro+rd*travel;
    if(travel<24.) {
        vec2 grid=abs(fract(pos.xz*1.4)-.5);
        float edge=min(grid.x,grid.y);
        float width=.007+travel*.0017;
        col+=palette(pos.z*.017+t*.02)*lineGlow(edge,width)*exp(-travel*.10)*.7;
        col+=palette(.6+pos.z*.03)*exp(-abs(fract(pos.z*.12+t*.13)-.5)*75.)*.2;
    }
    float sun=length(p-vec2(0,.28));
    col+=palette(.18)*lineGlow(abs(sun-.33-.025*u_audio.x),.002)*.55;
    col+=palette(.32)*exp(-sun*3.)*.08;
    vec2 st=p*50.; vec2 cell=floor(st); vec2 f=fract(st)-.5;
    float star=step(.984,hash21(cell+u_seed));
    col+=vec3(.3,.6,1)*star*exp(-length(f)*40.)*smoothstep(.05,.8,p.y);
    return min(col,vec3(14));
}
