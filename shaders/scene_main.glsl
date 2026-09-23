vec3 scene(int id,vec2 p) {
    if(id==0) return sceneCrystal(p);
    if(id==1) return sceneTunnel(p);
    if(id==2) return sceneKaleido(p);
    if(id==3) return sceneNebula(p);
    if(id==4) return sceneVortex(p);
    return sceneTerrain(p);
}
void main() {
    vec2 p=(gl_FragCoord.xy*2.-u_resolution)/min(u_resolution.x,u_resolution.y);
    float calm=mix(1.,.25,u_pulse.w);
    p*=1.-u_pulse.x*.025*calm;
    p+=u_pulse.x*.006*calm*vec2(sin(u_time*31.),cos(u_time*27.));
    vec3 c=scene(u_scene,p);
    if(u_transition<.999) {
        float transition=smoothstep(0.,1.,u_transition);
        vec2 q=rot((1.-transition)*.06)*p*(1.+.1*transition);
        c=mix(scene(u_previous,q),c,transition);
    }
    // Detected transients launch segmented shockwaves into the foreground.
    // Exponential beat decay doubles as a smooth, sound-locked particle clock.
    float pulse=max(u_pulse.x,.0001);
    float radius=.16-log(pulse)*.34;
    float angle=atan(p.y,p.x);
    float segments=.23+.77*pow(.5+.5*sin(angle*12.+u_motion*.8),4.);
    float shock=lineGlow(abs(length(p)-radius),.0025)*pow(pulse,.6)*segments;
    c+=palette(angle*.06+u_motion*.02+.4)*shock*(.35+.55*u_audio.x)*calm;
    c*=.56+.54*u_audio.w;
    fragColor=vec4(max(c,vec3(0)),1);
}
