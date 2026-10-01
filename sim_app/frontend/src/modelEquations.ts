/** Display notation for the existing Python models; no numerical computation. */
export const modelEquations = {
  etch: {
    absorbedPower: [
      String.raw`P_{\mathrm{abs}} = P_{\mathrm{fwd}} (1-r)\,\eta D`,
    ],
    particleBalance: [
      String.raw`n_{\mathrm{Ar}}\,k_{\mathrm{iz}}(T_e) = \frac{u_{\mathrm{B}} A_{\mathrm{eff}}}{V}`,
      String.raw`u_{\mathrm{B}} = \sqrt{\frac{eT_e}{m_{\mathrm{Ar}}}}`,
    ],
    powerBalance: [
      String.raw`P_{\mathrm{abs}} = n_e e\,u_{\mathrm{B}} A_{\mathrm{eff}}(E_c + 7.2T_e) + P_{\mathrm{diss}}`,
    ],
    ionEnergy: [
      String.raw`V_s = |V_{\mathrm{bias}}| + \frac{T_e}{2}\ln\!\left(\frac{m_{\mathrm{Ar}}}{2\pi m_e}\right)`,
      String.raw`E_i = \frac{T_e}{2} + \frac{V_s}{1+s_{\mathrm{CL}}/\lambda_i}`,
    ],
    surfaceRemoval: [
      String.raw`a = \frac{s\,\Gamma_{\mathrm{X}}}{N_s}`,
      String.raw`b = k_{\mathrm{des}} + k_{\mathrm{chem}} + \frac{\Gamma_i Y_{\mathrm{assist}}}{N_s}`,
      String.raw`\frac{\mathrm{d}\theta}{\mathrm{d}t} = a(1-\theta)-b\theta,\qquad \theta(0)=0`,
      String.raw`J(t) = (N_s k_{\mathrm{chem}} + \Gamma_i Y_{\mathrm{assist}})\,\theta(t) + \Gamma_i Y_{\mathrm{sputter}}`,
      String.raw`d(t) = \frac{10^9}{N_{\mathrm{target}}}\int_0^t J(\tau)\,\mathrm{d}\tau`,
    ],
    selectivity: [
      String.raw`Y(E) = Y_{\mathrm{scale}}\max\!\left(\sqrt{\frac{E}{E_{\mathrm{th}}}}-1,\,0\right)`,
      String.raw`d_{\mathrm{mask}}(t) = \frac{10^9\Gamma_i Y_{\mathrm{mask}}\,t}{N_{\mathrm{mask}}}`,
      String.raw`S = \frac{R_{\mathrm{target,ss}}}{R_{\mathrm{mask,ss}}}`,
    ],
    uniformity: [
      String.raw`q = \frac{r^2}{R_{\mathrm{w}}^2}`,
      String.raw`\Gamma_i(q) = \bar{\Gamma}_i\!\left[1+a_{\mathrm{radial}}\left(\frac{1}{2}-q\right)\right]`,
      String.raw`\mathrm{NU} = \frac{d_{\max}-d_{\min}}{2\bar{d}_{\mathrm{area}}}\times 100\%`,
    ],
  },
  ald: {
    chamberPressure: [
      String.raw`\frac{\mathrm{d}P_i}{\mathrm{d}t} = \frac{u_i-P_i}{\tau_i}`,
    ],
    transport: [
      String.raw`\bar{v}_i = \sqrt{\frac{8k_{\mathrm{Boltz}}T}{\pi m_i}}`,
      String.raw`D_i = \frac{2H}{3}\,\bar{v}_i`,
      String.raw`\frac{\partial p_i}{\partial t} = D_i\frac{\partial^2p_i}{\partial x^2} - \frac{2qk_{\mathrm{Boltz}}T}{H}\,r_i`,
    ],
    surfaceGrowth: [
      String.raw`k_i = \frac{s_i(T)}{q\sqrt{2\pi m_i k_{\mathrm{Boltz}}T}}`,
      String.raw`r_{\mathrm{A}} = k_{\mathrm{A}}p_{\mathrm{A}}(1-\theta)`,
      String.raw`r_{\mathrm{B}} = k_{\mathrm{B}}p_{\mathrm{B}}\theta`,
      String.raw`\frac{\mathrm{d}\theta}{\mathrm{d}t} = r_{\mathrm{A}}-r_{\mathrm{B}},\qquad \frac{\mathrm{d}z}{\mathrm{d}t} = r_{\mathrm{B}}`,
      String.raw`h_1(x) = g_{\mathrm{sat}}\,z(x)`,
    ],
    temperature: [
      String.raw`s_i(T) = s_i(T_{\mathrm{ref}})\exp\!\left[-\frac{E_a}{k_{\mathrm{Boltz}}}\left(\frac{1}{T}-\frac{1}{T_{\mathrm{ref}}}\right)\right]`,
    ],
    thickness: [
      String.raw`h_N(x) = N\,h_1(x)`,
      String.raw`C = \frac{h_1(\mathrm{deep})}{h_1(\mathrm{near})}\times 100\%`,
    ],
    purge: [
      String.raw`O = \int_0^{t_{\mathrm{end}}}\min\!\left(P_{\mathrm{A}}(t),P_{\mathrm{B}}(t)\right)\,\mathrm{d}t`,
      String.raw`P_{\mathrm{residual}} = P_{\mathrm{A}}(t_{\mathrm{end}}) + P_{\mathrm{B}}(t_{\mathrm{end}})`,
    ],
  },
} as const;
