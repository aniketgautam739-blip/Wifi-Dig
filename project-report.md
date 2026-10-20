# DESIGN AND PERFORMANCE ANALYSIS OF A DC–DC BUCK CONVERTER USING LTspice

**Independent Electrical Engineering Simulation Project**

**Project Author:** [Your Full Name]\
**Date:** [Month, Year]\
**Software:** LTspice\
**Project Type:** Independent simulation-based engineering investigation

---

## ABSTRACT

This project investigates the design and simulated performance of a DC–DC buck converter using LTspice. A buck converter is a switching power-electronic circuit that reduces a DC input voltage to a lower DC output voltage. Such converters are commonly used in battery-powered devices, embedded systems, voltage regulators, and other electronic equipment.

The investigation examines the effects of duty cycle, switching frequency, inductance, and capacitance on converter behavior. Transient simulations are used to observe output voltage and current waveforms and to estimate current and voltage ripple. Input and output power are also investigated to understand the concept of conversion efficiency.

The converter was simulated using a MOSFET, diode, inductor, capacitor, and resistive load. A reported input voltage of 12 V and an output voltage of approximately 4.89 V were obtained under the baseline operating conditions. Additional experiments explored changes in duty cycle, switching period, inductance, and capacitance.

The project demonstrates how circuit simulation can be used to investigate switching-converter behavior, compare theoretical predictions with simulated results, and identify the effects of component selection on power-conversion performance. The findings are limited to the accuracy of the circuit model and the measurements obtained in simulation.

## 1. INTRODUCTION

Electrical and electronic systems often require a stable DC voltage that differs from the voltage supplied by a battery, power adapter, or another DC source. DC–DC converters provide a method of converting one DC voltage level into another.

A buck converter is a step-down switching converter. It uses a controlled switching device, an energy-storage inductor, a diode or equivalent current path, and a capacitor to produce a lower DC output voltage.

Unlike a simple resistive voltage divider, a switching converter transfers energy through controlled switching and energy-storage components. Its performance depends on operating conditions and component parameters.

In this project, LTspice is used to construct and simulate a buck-converter circuit. Different operating parameters are varied to investigate their effects on output voltage, current ripple, and estimated conversion efficiency.

The project provides practical experience in circuit simulation, measurement, data analysis, and the application of electrical engineering theory.

## 2. PROJECT OBJECTIVES

The objectives of this project are:

1. To construct and simulate a DC–DC buck converter using LTspice.
2. To investigate the relationship between duty cycle and average output voltage.
3. To examine the effect of switching frequency on converter waveforms.
4. To investigate the relationship between inductance and inductor current ripple.
5. To examine the effect of output capacitance on output-voltage ripple.
6. To estimate input power, output power, and conversion efficiency.
7. To compare simulated behavior with theoretical predictions.
8. To develop practical skills in circuit design, simulation, troubleshooting, and technical reporting.

## 3. THEORETICAL BACKGROUND

### 3.1 Principle of operation

A buck converter controls the transfer of energy from a DC source to a load by rapidly switching a semiconductor device on and off.

During the switch-on interval, energy is transferred from the input through the inductor to the output. During the switch-off interval, the inductor continues to supply current through the circuit's freewheeling path.

The output capacitor helps reduce voltage fluctuations, while the inductor limits rapid changes in current.

### 3.2 Duty cycle and output voltage

Duty cycle is the fraction of each switching period during which the switching device is on.

It is defined as:

D = Ton / Ts

where:

- D is the duty cycle.
- Ton is the switch-on time.
- Ts is the total switching period.

For an ideal buck converter operating in steady state under continuous-conduction conditions, the average output voltage is approximately:

Vout = D × Vin

For an input voltage of 12 V and a duty cycle of 0.40:

Vout = 0.40 × 12 = 4.8 V

This theoretical value provides a reference for comparison with the simulated output voltage.

### 3.3 Switching frequency

Switching frequency is the number of switching cycles per second:

fs = 1 / Ts

For a switching period of 40 microseconds:

fs = 1 / (40 × 10^-6) = 25 kHz

Increasing switching frequency can reduce current ripple under otherwise comparable ideal operating conditions. However, switching losses may also increase in a practical converter.

### 3.4 Inductor current ripple

The inductor stores energy in its magnetic field and limits changes in current. Current ripple is the difference between the maximum and minimum inductor current over a switching cycle:

ΔIL = IL(max) − IL(min)

A larger inductance generally reduces current ripple when other operating conditions remain constant.

### 3.5 Output-voltage ripple and capacitance

The output capacitor stores electrical energy and helps maintain the output voltage between switching events.

Output-voltage ripple is defined as:

ΔVout = Vout(max) − Vout(min)

For otherwise comparable operating conditions, increasing capacitance generally reduces the capacitive component of output-voltage ripple. Equivalent series resistance, circuit topology, and transient behavior can also influence the measured ripple.

### 3.6 Conversion efficiency

Conversion efficiency expresses the fraction of input power delivered to the output:

η = (Pout / Pin) × 100%

where Pin is input power and Pout is output power.

The power values should ideally be measured as average instantaneous power over the same steady-state interval:

Pin = average[Vin(t) × Iin(t)]

Pout = average[Vout(t) × Iout(t)]

The current direction and sign convention must be handled consistently. A realistic efficiency estimate also depends on whether the simulation includes semiconductor conduction losses, switching losses, inductor resistance, and other non-ideal effects.

## 4. CIRCUIT DESIGN AND SIMULATION METHOD

The converter was constructed in LTspice using a DC input source, MOSFET switching device, diode, inductor, output capacitor, and resistive load.

The circuit was analyzed using transient simulation to observe how voltage and current changed with time.

### Baseline operating conditions

| Parameter                 | Baseline setting       |
| ------------------------- | ---------------------- |
| Input voltage             | 12 V                   |
| Duty cycle                | 40%                    |
| Switching period          | 40 µs                  |
| Switching frequency       | 25 kHz                 |
| Transient duration        | 5 ms                   |
| Switching device          | MOSFET                 |
| Freewheeling path         | Diode                  |
| Energy-storage components | Inductor and capacitor |
| Load                      | Resistive load         |

The inductor, capacitor, load resistance, and semiconductor model values should be documented using the actual values in the saved LTspice schematic.

### Experimental procedure

The circuit was first simulated under the baseline conditions. One parameter was then varied at a time while the other parameters were kept constant.

The duty cycle, switching period, inductance, and capacitance were investigated separately. Waveforms were inspected after the initial transient, with measurements intended to use the interval from 4.5 ms to 5 ms where the circuit had reached steady state.

The measurements were recorded in tables and compared with theoretical expectations. The investigation was simulation-based; no physical hardware testing was performed.

##

The remaining numerical readings should be obtained from the saved simulation before the table is finalized.

### 5.2 Switching-frequency investigation

The switching period was changed while the other circuit settings were intended to remain constant.

| Switching period | Switching frequency | Observation |
| ---------------- | ------------------: | ----------- |
| 40 µs            |              25 kHz | Simulated   |
| 20 µs            |              50 kHz | Simulated   |
| 10 µs            |             100 kHz | Simulated   |

The output voltage was reported to change relatively little across these tests. This is consistent with the fact that the ideal average output voltage is primarily determined by duty cycle and input voltage. Frequency-related effects are more clearly investigated by comparing ripple, switching losses, and other waveform characteristics.

### 5.3 Inductance investigation

The inductor current ripple was calculated using the difference between the peak and valley current.

| Run |      Inductance | Peak current | Valley current | Calculated ripple |
| --- | --------------: | -----------: | -------------: | ----------------: |
| 1   |           68 µH |      1.450 A |            0 A |           1.450 A |
| 2   | To be confirmed |      0.860 A |        0.030 A |           0.830 A |
| 3   | To be confirmed |      0.780 A |        0.238 A |           0.542 A |

The recorded ripple decreases across these three runs. This is consistent with the expected effect of increasing inductance, provided the other operating conditions are comparable. The inductance values for runs 2 and 3 must be confirmed before drawing a final quantitative conclusion.

### 5.4 Capacitance investigation

The following readings were recorded during the capacitance tests. Their units and measurement node must be verified before the results are treated as output-voltage ripple.

| Capacitor setting              | Highest reported reading | Lowest reported reading |        Difference |
| ------------------------------ | -----------------------: | ----------------------: | ----------------: |
| 100 µF                         |                      830 |                      90 | 740 reading-units |
| 200 µF                         |                      855 |                     120 | 735 reading-units |
| Third setting, reported as 450 |                      690 |                       6 | 684 reading-units |

These readings are not yet confirmed voltage-ripple measurements. The trace must be verified as output voltage rather than current, and the third capacitance setting must be checked against the actual schematic. This experiment should be repeated or corrected if necessary before a final conclusion is written.

### 5.5 Output power and efficiency investigation

The following values were reported during the initial efficiency investigation.

| Parameter      | Reported value |
| -------------- | -------------: |
| Input voltage  |           12 V |
| Input current  |          0.7 A |
| Output voltage |         4.89 V |
| Output current |       0.4583 A |

Using these reported values:

Pin ≈ 12 × 0.7 = 8.4 W

Pout ≈ 4.89 × 0.4583 ≈ 2.24 W

The simple average-value calculation gives an estimated efficiency of approximately 26.7%. This is a preliminary estimate rather than a validated final result. The input-current measurement, output-current measurement, measurement interval, and component models should be checked. For greater accuracy, average instantaneous input and output power should be measured over the same steady-state interval.

## 6. DISCUSSION

The duty-cycle investigation showed that the simulated output voltage was close to the theoretical prediction at the reported 40% and 60% duty-cycle settings. This illustrates the relationship between duty cycle and average output voltage in a buck converter.

The switching-frequency investigation indicated that changing the switching period did not substantially change the average output voltage in the tested cases. Further analysis of ripple and semiconductor losses would provide a more complete comparison.

The inductance measurements showed a reduction in calculated current ripple across the three recorded runs. This behavior is consistent with the expected role of inductance in limiting current variation, although the component settings for two runs need to be confirmed.

The capacitance investigation requires additional verification because the reported values have not yet been confirmed as output-voltage readings. Accurate identification of the measured trace and its units is essential for a valid engineering conclusion.

The initial efficiency estimate was substantially lower than might be expected from a well-designed buck converter. Potential causes include measurement or sign-convention errors, mismatched measurement intervals, model characteristics, and losses represented by the circuit. The efficiency calculation should therefore be repeated before it is presented as a final result.

These issues demonstrate an important aspect of engineering work: unexpected results should be investigated rather than changed simply to match theoretical expectations.

## 7. LIMITATIONS

This project has several limitations:

1. The investigation was conducted using circuit simulation rather than a physical prototype.
2. The accuracy of the results depends on the LTspice models and the selected component parameters.
3. Some experimental values require verification before quantitative conclusions can be finalized.
4. The efficiency estimate requires more rigorous power measurement.
5. Real-world effects such as component temperature, wiring resistance, electromagnetic interference, and hardware tolerances were not experimentally evaluated.

## 8. CONCLUSION

This project used LTspice to investigate the behavior of a DC–DC buck converter under different operating conditions. The investigation covered duty cycle, switching frequency, inductance, capacitance, and power-conversion efficiency.

The reported output voltage of approximately 4.9 V at a 12 V input and 40% duty cycle was close to the ideal theoretical value of 4.8 V. The current-ripple measurements also illustrated the importance of inductor selection.

The project developed practical experience in constructing a circuit simulation, interpreting waveforms, calculating electrical quantities, and comparing theoretical expectations with simulated behavior.

Further work will focus on verifying the remaining component settings, repeating uncertain measurements, improving the efficiency calculation, and investigating realistic component losses. A future extension could involve constructing a physical prototype and comparing its measurements with the LTspice results.

## 9. REFERENCES

Add the exact sources consulted for your research. Suitable source types include:

1. LTspice official documentation and help resources.
2. A power electronics textbook discussing DC–DC converters.
3. Datasheets for the MOSFET and diode models used in the circuit.
4. Manufacturer documentation for the inductor and capacitor models, where applicable.

Only include sources that you actually consulted. Record the title, author or organization, publication date where available, and URL or publication details.

## APPENDIX A: SIMULATION EVIDENCE

Insert the following genuine screenshots:

- Complete LTspice circuit schematic.
- Duty-cycle experiment waveforms.
- Switching-frequency experiment waveforms.
- Inductor-current waveforms for each inductance setting.
- Verified output-voltage waveforms for the capacitance experiment.
- Input and output voltage/current waveforms used for the efficiency calculation.

Each screenshot should have a figure number, a descriptive caption, and the relevant circuit settings.

## APPENDIX B: REPRODUCIBILITY

Include the original LTspice schematic and a table of the component values used in the final simulations. This enables another person to open the circuit, rerun the simulation, and compare the results with those presented in the report.