// AFTERBURN / three procedural worlds. Common uniforms and helpers are supplied
// by visualizer.frag. Every scene returns linear HDR light for the shared bloom.

vec3 cryRotate(vec3 p) {
    p.xz = rot(u_motion * 0.19 + u_seed * 0.071) * p.xz;
    p.yz = rot(0.43 + u_motion * 0.127) * p.yz;
    p.xy = rot(0.19 * sin(u_motion * 0.13)) * p.xy;
    return p;
}

float cryHull(vec3 p) {
    vec3 a = abs(cryRotate(p));
    float size = 0.65 + 0.06 * u_audio.x + 0.014 * u_pulse.x;
    // The twenty supporting planes of an icosahedron produce real triangular
    // facets; this remains a conservative distance bound for sphere tracing.
    float corners = (a.x + a.y + a.z) * 0.57735027;
    float sides = max(a.y * 0.35682209 + a.z * 0.93417236,
                  max(a.x * 0.35682209 + a.y * 0.93417236,
                      a.x * 0.93417236 + a.z * 0.35682209));
    return max(corners, sides) - size - 0.008;
}

float cryFacetEdge(vec3 p) {
    vec3 a = abs(cryRotate(p));
    vec4 best = vec4((a.x + a.y + a.z) * 0.57735027,
        a.y * 0.35682209 + a.z * 0.93417236,
        a.x * 0.35682209 + a.y * 0.93417236,
        a.x * 0.93417236 + a.z * 0.35682209);
    vec4 next = best - 2.0 * vec4(min(a.x, min(a.y, a.z)) * 0.57735027,
        min(a.y * 0.35682209, a.z * 0.93417236),
        min(a.x * 0.35682209, a.y * 0.93417236),
        min(a.x * 0.93417236, a.z * 0.35682209));
    float first = -1000.0;
    float second = -1000.0;
    for (int i = 0; i < 4; ++i) {
        float v = best[i];
        if (v > first) { second = first; first = v; }
        else second = max(second, v);
    }
    second = max(second, max(max(next.x, next.y), max(next.z, next.w)));
    return max(first - second, 0.0);
}

float cryRing(vec3 p, float index) {
    p.xz = rot(index * 1.14 + u_motion * (0.083 + index * 0.021)) * p.xz;
    p.yz = rot(0.72 + index * 0.81 + 0.13 * sin(u_motion * 0.17 + index)) * p.yz;
    float radius = 1.03 + index * 0.17;
    float a = atan(p.y, p.x);
    radius += 0.020 * sin(a * (6.0 + index * 2.0) + u_motion * 0.7) * u_audio.y;
    return length(vec2(length(p.xy) - radius, p.z)) - (0.006 + 0.004 * u_audio.z);
}

vec2 cryMap(vec3 p) {
    vec2 res = vec2(cryHull(p), 0.0);
    for (int j = 0; j < 3; ++j) {
        float d = cryRing(p, float(j));
        if (d < res.x) res = vec2(d, float(j + 1));
    }
    return res;
}

vec3 cryNormal(vec3 p, bool ring) {
    vec2 e = vec2(0.0015, 0.0);
    if (ring) {
        return normalize(vec3(
            cryMap(p + e.xyy).x - cryMap(p - e.xyy).x,
            cryMap(p + e.yxy).x - cryMap(p - e.yxy).x,
            cryMap(p + e.yyx).x - cryMap(p - e.yyx).x));
    }
    return normalize(vec3(
        cryHull(p + e.xyy) - cryHull(p - e.xyy),
        cryHull(p + e.yxy) - cryHull(p - e.yxy),
        cryHull(p + e.yyx) - cryHull(p - e.yyx)));
}

vec3 cryEnvironment(vec3 r) {
    float a = atan(r.z, r.x);
    float sweep = sin(a * 3.0 + r.y * 4.0 + u_motion * 0.13);
    vec3 env = palette(a * 0.12 + r.y * 0.3 + u_seed * 0.019) *
        (0.025 + 0.34 * pow(max(sweep, 0.0), 9.0));
    float lightStrip = pow(max(cos(a * 4.0 + r.y * 3.0 + u_motion * 0.06), 0.0), 40.0);
    env += palette(a * 0.19 + 0.6) * lightStrip * 1.3;
    float upperSoftbox = pow(max(dot(r, normalize(vec3(-0.5, 0.8, 0.2))), 0.0), 28.0);
    float sideSoftbox = pow(max(dot(r, normalize(vec3(0.8, -0.15, 0.5))), 0.0), 65.0);
    env += vec3(0.64, 0.85, 1.0) * upperSoftbox * 2.3;
    env += vec3(1.0, 0.24, 0.48) * sideSoftbox * 2.8;
    return env;
}

vec3 sceneCrystal(vec2 p) {
    float radial = length(p);
    vec3 col = vec3(0.004, 0.006, 0.017);
    col += palette(0.55 + u_seed * 0.03) * 0.07 * exp(-radial * radial * 1.3);

    // Distant flecks stay subordinate to the rotating sculpture.
    vec2 sky = p * 15.0 + vec2(u_motion * 0.009, -u_motion * 0.007);
    vec2 cell = floor(sky);
    float id = hash21(cell + u_seed);
    vec2 center = vec2(hash21(cell + 3.1), hash21(cell + 9.7)) * 0.66 + 0.17;
    float starD = length(fract(sky) - center);
    col += vec3(0.18, 0.29, 0.45) * exp(-starD * starD * 1450.0) * step(0.89, id);

    vec3 ro = vec3(0.0, 0.0, 3.85);
    vec3 rd = normalize(vec3(p * 0.82, -2.15));
    float ray = 1.65;
    float halo = 0.0;
    vec2 hit = vec2(1.0, 0.0);
    bool found = false;
    for (int k = 0; k < 58; ++k) {
        vec3 pos = ro + rd * ray;
        hit = cryMap(pos);
        float ringD = min(cryRing(pos, 0.0), min(cryRing(pos, 1.0), cryRing(pos, 2.0)));
        halo += 0.0016 * exp(-abs(ringD) * 18.0);
        if (hit.x < 0.0015) { found = true; break; }
        ray += max(hit.x * 0.82, 0.001);
        if (ray > 6.0) break;
    }
    col += palette(radial * 0.25 + u_motion * 0.018) * halo * (1.4 + u_audio.x * 2.0);

    if (found) {
        vec3 pos = ro + rd * ray;
        bool ring = hit.y > 0.5;
        vec3 n = cryNormal(pos, ring);
        vec3 reflected = reflect(rd, n);
        float fresnel = pow(1.0 - max(dot(-rd, n), 0.0), 3.5);
        if (ring) {
            float along = atan(pos.y, pos.x);
            float traveling = pow(0.5 + 0.5 * sin(along * 9.0 - u_motion * 1.9 + hit.y), 13.0);
            col = palette(hit.y * 0.19 + 0.06 * along + u_seed * 0.015) *
                (1.25 + 1.8 * traveling + u_pulse.x * 0.5);
            col += vec3(0.28, 0.43, 0.52) * fresnel;
        } else {
            vec3 q = cryRotate(pos);
            float faceColor = dot(abs(cryRotate(n)), vec3(0.31, 0.49, 0.71));
            vec3 jewel = palette(faceColor + u_seed * 0.018 + u_motion * 0.009);
            float light = max(dot(n, normalize(vec3(-0.55, 0.85, 1.0))), 0.0);
            float rim = pow(max(dot(n, normalize(vec3(0.9, -0.2, -0.5))), 0.0), 4.0);
            float stripe = abs(sin((q.x + q.y * 0.67 - q.z * 0.3) * 64.0));
            float engraving = (1.0 - smoothstep(0.02, 0.11, stripe)) * 0.055;
            float internal = pow(max(0.0, 1.0 - length(q.xy) * 1.25), 3.0);
            col = jewel * (0.045 + light * 0.15 + internal * 0.13 * u_audio.x);
            col += cryEnvironment(reflected) * (0.84 + 0.58 * fresnel);
            col += jewel * (fresnel * 0.72 + rim * 0.8 + engraving);
            float facetEdge = exp(-cryFacetEdge(pos) * 230.0);
            col += mix(jewel, vec3(0.25, 0.8, 1.0), 0.35) * facetEdge * (0.75 + u_audio.y * 0.6);
            col += vec3(0.52, 0.82, 1.0) * pow(max(dot(reflected, normalize(vec3(-0.5, 0.7, 0.8))), 0.0), 70.0) * 2.5;
        }
    }
    return clamp(col, 0.0, 12.0);
}

float nebFbm(vec2 p) {
    float sum = 0.0;
    float gain = 0.52;
    mat2 twist = mat2(0.80, -0.60, 0.60, 0.80);
    for (int i = 0; i < 5; ++i) {
        sum += gain * noise2(p);
        p = twist * p * 2.07 + vec2(11.3, 7.8);
        gain *= 0.48;
    }
    return sum;
}

vec3 nebStars(vec2 p, float depth) {
    vec2 q = p * (10.0 + depth * 13.0);
    q += vec2(u_motion * (0.015 + depth * 0.012), -u_motion * 0.009 * depth);
    vec2 cell = floor(q);
    float id = hash21(cell + depth * 41.7 + u_seed);
    vec2 center = 0.15 + 0.7 * vec2(hash21(cell + 12.3 + depth), hash21(cell + 47.1 + depth));
    vec2 d = fract(q) - center;
    float ds = dot(d, d);
    float core = exp(-ds * (1900.0 + depth * 600.0));
    float twinkle = 0.7 + 0.3 * sin(u_motion * (0.13 + id * 0.2) + id * 38.0);
    float prominence = smoothstep(0.95, 1.0, id);
    float flare = exp(-abs(d.x) * 120.0 - abs(d.y) * 13.0) +
                  exp(-abs(d.y) * 120.0 - abs(d.x) * 13.0);
    vec3 tint = mix(vec3(0.42, 0.63, 1.0), vec3(1.0, 0.69, 0.41), hash21(cell + 4.9));
    return tint * (core * 1.8 + flare * prominence * 0.27) * step(0.83, id) * twinkle /
        (1.0 + depth * 0.42);
}

vec3 sceneNebula(vec2 p) {
    float t = u_motion * 0.055;
    vec2 view = rot(t * 0.13 + u_seed * 0.011) * p;
    vec3 col = vec3(0.003, 0.005, 0.016);
    col += nebStars(view * 0.94, 2.0) * 0.48;
    col += nebStars(view, 1.0) * 0.7;

    // Offset translucent sheets create parallax and dark dust between filaments.
    for (int layer = 0; layer < 5; ++layer) {
        float z = float(layer);
        vec2 q = view * (1.05 + z * 0.21);
        q = rot(0.18 * z + t * (0.05 + z * 0.012)) * q;
        q += vec2(0.28 * sin(t * 0.7 + z), 0.13 * cos(t * 0.5 + z * 2.0));
        float radius = length(q);
        q = rot(0.7 / (radius + 0.45) + z * 0.25) * q;
        vec2 warp = vec2(nebFbm(q * 1.1 + vec2(t, z * 5.9)),
                         nebFbm(q * 1.1 + vec2(8.3 + z * 3.1, -t * 0.6)));
        float field = nebFbm(q * 2.1 + warp * 2.2 + z * 9.2);
        float fine = nebFbm(q * 4.8 + warp * 3.4 + vec2(-t * 0.35, z * 7.1));
        float lane = q.y + 0.31 * sin(q.x * 1.7 + z * 0.8 + t * 0.17);
        float band = exp(-lane * lane * (1.4 + z * 0.15));
        float dust = smoothstep(0.23, 0.66, field);
        float contour = exp(-abs(field - (0.48 + 0.04 * sin(t * 0.8 + z))) * 36.0);
        float silk = pow(max(fine, 0.0), 2.1) * contour;
        float density = band * dust;
        vec3 tint = palette(field * 0.7 + z * 0.135 + u_seed * 0.027 + t * 0.015);
        vec3 hotTint = mix(tint, vec3(0.47, 0.71, 1.0), 0.25);
        col *= 1.0 - density * 0.075;
        col += tint * density * 0.23;
        col += hotTint * silk * band * (0.6 + u_audio.x * 0.6 + spec(z * 0.19) * 0.32);
    }

    // A luminous, slowly moving heart lights the gas without filling every pixel.
    vec2 heart = view - vec2(0.12 * sin(t * 0.6), 0.12 * cos(t * 0.39));
    float glow = exp(-dot(heart, heart) * 4.7);
    col += palette(0.13 + u_seed * 0.017) * glow * (0.08 + u_audio.x * 0.13);
    col += nebStars(view * 1.08, 0.0) * (0.9 + u_audio.z * 0.35);
    return clamp(col, 0.0, 12.0);
}

vec2 kalWedge(vec2 p, float wedges) {
    float radius = length(p);
    float slice = 6.28318530718 / wedges;
    float angle = abs(mod(atan(p.y, p.x) + slice * 0.5, slice) - slice * 0.5);
    return vec2(cos(angle), sin(angle)) * radius;
}

float kalGlow(float distance, float width) {
    float v = width / max(abs(distance), width * 0.35);
    return min(v * v, 7.0);
}

vec3 sceneKaleido(vec2 p) {
    float t = u_motion * 0.11;
    float radius = length(p);
    float music = 0.5 * u_audio.x + 0.25 * u_audio.y + 0.25 * u_audio.z;
    vec2 spin = rot(t * 0.18 + u_seed * 0.021) * p;
    // Mirroring occurs before each recursive fold, preserving a deliberate
    // cathedral-window silhouette through even the most intricate passages.
    vec2 q = kalWedge(spin, 12.0);
    vec3 col = vec3(0.004, 0.005, 0.016);
    col += palette(radius * 0.23 + t * 0.017) * exp(-radius * radius * 0.9) * 0.045;
    float scale = 1.0;
    float phase = 0.19 * sin(t * 0.4) + 0.015 * u_pulse.x;

    for (int i = 0; i < 7; ++i) {
        float level = float(i);
        q = abs(q) - vec2(0.41 + 0.045 * sin(t * 0.23 + level * 0.7), 0.12 + phase);
        q = rot(0.64 + 0.11 * sin(t * 0.19 + level * 0.31)) * q;
        q *= 1.48;
        scale *= 1.48;

        float circle = abs(length(q) - (0.34 + 0.025 * sin(t * 0.55 + level)));
        float diamond = abs((abs(q.x) + abs(q.y)) * 0.70710678 - 0.26);
        float ribbon = min(circle, diamond * 1.25);
        float width = (0.0044 + 0.0024 * spec(level / 7.0)) * (1.0 + level * 0.04);
        float fine = kalGlow(ribbon, width);
        float soft = exp(-ribbon * 21.0) * 0.11;
        float keep = exp(-dot(q, q) * 0.11);
        vec3 tint = palette(level * 0.127 + length(q) * 0.11 + t * 0.026 + u_seed * 0.019);
        float levelStrength = 0.52 / (1.0 + level * 0.21);
        col += tint * (fine * (0.37 + music * 0.2) + soft) * keep * levelStrength;

        // Tiny pearls at fold intersections, softened before shared bloom.
        float bead = length(abs(q) - vec2(0.185));
        col += mix(tint, vec3(0.75, 0.87, 1.0), 0.35) * exp(-bead * bead * 950.0) *
            (0.22 + u_audio.z * 0.22) / (1.0 + level * 0.15);
    }

    float angle = atan(spin.y, spin.x);
    float petals = 0.57 + 0.12 * cos(angle * 12.0);
    float rosette = abs(radius - petals * (1.0 + 0.055 * u_audio.x));
    vec3 edgeTint = palette(0.57 + t * 0.021 + u_seed * 0.019);
    col += edgeTint * kalGlow(rosette, 0.0032) * 0.16;
    col += palette(0.18 + t * 0.018) * exp(-radius * radius * 32.0) * 0.26;
    col *= 0.58 + 0.42 * exp(-radius * radius * 0.16);
    return clamp(col, 0.0, 12.0);
}
