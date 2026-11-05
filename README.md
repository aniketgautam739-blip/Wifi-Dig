# Aniket's WiFi Dig
### Router & Network Intelligence Suite

**A Python-Based Network Diagnostics, Router Analysis & Electrical Engineering Utility**

![Python](https://img.shields.io/badge/Python-3.x-blue?logo=python)
![Platform](https://img.shields.io/badge/Platform-Windows-lightgrey)
![GUI](https://img.shields.io/badge/Interface-Tkinter-orange)
![Project](https://img.shields.io/badge/Type-Network%20Diagnostics-informational)

---

## 1. Project Overview

**Aniket's WiFi Dig** is a Python-based network intelligence and diagnostic application designed to provide a comprehensive understanding of local network infrastructure, router performance, connected devices, and the engineering principles behind wireless communication.

The project brings several traditionally separate networking utilities into one graphical application. Instead of relying on multiple command-line tools and websites, users can access network information, perform diagnostics, explore router specifications, examine connected devices, and understand the technical principles governing network performance through a unified interface.

The application also incorporates concepts from electrical engineering, radio frequency (RF) communication, and digital networking to connect practical network diagnostics with the underlying engineering theory.

**The central idea:** To make network infrastructure more understandable by combining practical diagnostics, technical calculations, and engineering knowledge in one application.

## 2. Why I Developed This Project

My interest in electrical and computer engineering motivated me to explore how everyday network infrastructure actually operates.

Wi-Fi is something people use every day, but the engineering behind it is considerably more complex. A wireless router involves radio-frequency transmission, electromagnetic waves, signal attenuation, modulation, bandwidth allocation, interference, and communication protocols.

I wanted to develop a tool that would help me investigate these systems beyond simply checking whether an internet connection was working.

I identified several areas worth exploring:

- How routers communicate with devices across a local network.
- How network performance can be measured and interpreted.
- How wireless signal strength affects connectivity.
- How IP and MAC addresses help identify network interfaces and devices.
- How router specifications relate to real-world performance.
- How RF principles and mathematical models explain wireless communication.
- How networking hardware contributes to electricity consumption and operating costs.

Rather than treating these as unrelated subjects, I designed WiFi Dig to bring them together into one application.

## 3. Core Features

### 3.1 Router Intelligence & Analysis

The router analysis component investigates the local network gateway and presents relevant technical information.

Depending on operating-system and router support, the application can examine:

- Default gateway information.
- Router IP address.
- MAC address identification.
- Manufacturer/vendor information.
- Available network services.
- DHCP-related information.
- HTTP response and server banner information.
- Router specifications through a manually maintained specification sheet.

The objective is to understand the router as a network device rather than simply viewing it as a source of internet connectivity.

### 3.2 Local Network Device Discovery

The application includes functionality for examining devices on the local network.

Network discovery helps demonstrate how devices communicate within a LAN (Local Area Network).

Relevant concepts include:

- Local IP addressing.
- MAC addressing.
- Network interfaces.
- Device identification.
- Gateway communication.
- Local network architecture.

This is particularly useful for understanding how computers, smartphones, routers, and other connected equipment coexist within the same network.

*Device identification depends on network permissions, device availability, and operating-system limitations.*

### 3.3 Wi-Fi Performance Diagnostics

WiFi Dig incorporates performance-monitoring functionality to help evaluate network connectivity.

| Measurement | Description |
|---|---|
| Download speed | Rate at which data is received |
| Upload speed | Rate at which data is transmitted |
| Ping | Round-trip network response time |
| Latency | Communication delay |
| Jitter | Variation in packet delay |
| Packet loss | Percentage of packets that fail to arrive |
| Signal strength | Wireless signal level where supported |
| Connection status | Current network connectivity information |

These measurements help distinguish different types of network problems.

For example, a connection may have high download speeds but still perform poorly during video calls because of latency, jitter, or packet loss.

### 3.4 Wi-Fi Signal & RF Engineering

One of the most interesting aspects of this project is its connection to radio-frequency engineering.

Wi-Fi communicates using electromagnetic waves. Its performance is affected by distance, obstacles, interference, frequency, and environmental conditions.

The application incorporates RF-related calculations and technical explanations involving:

- Signal strength measured in dBm.
- Signal-to-noise ratio (SNR).
- Signal attenuation.
- Frequency and wavelength.
- Wireless capacity.
- RF propagation concepts.

These concepts help connect the measurements displayed by the application to the physics of wireless communication.

### 3.5 Electrical Engineering Calculations

WiFi Dig also explores the relationship between networking hardware and electrical engineering.

The engineering component introduces calculations and concepts associated with:

- Voltage and current.
- Electrical power.
- Energy consumption.
- Power efficiency.
- Operating costs.
- RF and signal calculations.

This provides a connection between the software side of networking and the physical electrical systems that power communication equipment.

### 3.6 Router & Device Cost Analysis

Network equipment involves both initial purchasing expenses and continuing electricity costs.

The project incorporates equipment specifications and cost-related analysis to help users understand the financial side of operating network infrastructure.

The analysis considers:

- Equipment purchase costs.
- Rated power consumption.
- Estimated operating hours.
- Electricity tariffs.
- Estimated energy consumption.
- Long-term operating expenses.

These calculations are estimates based on supplied specifications and assumptions, not direct laboratory measurements.

### 3.7 Troubleshooting & Network Insights

The application is intended to make technical network information easier to interpret.

Instead of presenting measurements without context, it incorporates troubleshooting-oriented insights to help users understand possible connectivity and performance issues.

Examples include:

- Identifying possible latency-related problems.
- Understanding weak wireless signals.
- Recognizing potential network instability.
- Interpreting signal-to-noise ratios.
- Understanding the relationship between bandwidth and network performance.

## 4. Technical Concepts Behind the Project

The project combines several areas of computer networking and electrical engineering.

| Concept | Application |
|---|---|
| TCP/IP | Understanding network communication |
| LAN | Examining local network infrastructure |
| DHCP | Understanding automatic IP allocation |
| DNS | Understanding domain name resolution |
| MAC Address | Network interface identification |
| HTTP | Examining web-based router responses |
| RF Engineering | Understanding wireless transmission |
| SNR | Evaluating signal quality |
| dBm | Expressing signal power |
| Bandwidth | Understanding data transmission capacity |
| Electrical Power | Understanding equipment consumption |

## 5. Technologies Used

- **Python:** Main programming language.
- **Tkinter:** Graphical user interface development.
- **Operating-system networking utilities:** Retrieving local network information.
- **Socket programming:** Network communication and connectivity checks.
- **HTTP-related functionality:** Examining supported router responses.
- **Mathematical calculations:** RF, electrical, and network-performance analysis.

## 6. How the Application Is Useful

WiFi Dig has potential applications in several practical situations:

**Home Network Diagnostics**

Understanding connectivity issues, router information, and local network performance.

**Network Infrastructure Learning**

Exploring how routers, connected devices, IP addresses, and communication protocols work together.

**Wireless Communication Education**

Understanding RF concepts such as signal strength, attenuation, SNR, and wireless capacity.

**Electrical Engineering Education**

Connecting networking equipment with electrical power, energy consumption, and engineering calculations.

**Technical Troubleshooting**

Organizing network information to help investigate possible connectivity and performance issues.

## 7. Project Development & Learning Outcomes

Developing WiFi Dig helped me explore the intersection of software development, networking, and electrical engineering.

Some of the most valuable areas of learning included:

- Building a graphical application using Python.
- Understanding network gateways and local network architecture.
- Working with network information and communication protocols.
- Understanding the difference between signal strength and signal quality.
- Exploring RF engineering and wireless communication principles.
- Applying mathematical calculations to practical engineering problems.
- Designing an interface that organizes complex technical information.

More importantly, the project helped me understand that software can be used as a practical tool for investigating physical engineering systems.

## 8. Limitations & Technical Considerations

The accuracy and availability of certain measurements depend on the computer, network environment, operating system, router configuration, and available permissions.

Some router information may not be publicly accessible. Similarly, device discovery and signal measurements can be restricted by network configurations or hardware support.

RF calculations and estimated energy costs are models based on supplied inputs and assumptions. They should not automatically be interpreted as laboratory measurements.

The application is intended for educational purposes and authorized network diagnostics on networks the user owns or has permission to examine.

## 9. Future Improvements

Potential future development directions include:

- Historical network-performance tracking.
- Network diagnostic report generation.
- More detailed graphical signal analysis.
- Additional router compatibility.
- Expanded RF engineering calculations.
- Improved device information presentation.
- More advanced visualization of network performance.

## 10. Project Philosophy

I developed Aniket's WiFi Dig because I wanted to understand the technology behind something people use almost every day.

What initially appeared to be a simple networking project became an opportunity to explore how programming, electrical engineering, wireless communication, and mathematical modelling intersect.

The project represents my interest in going beyond using technology and learning how it actually works.

---

**Developed by Aniket Gautam**

*Independent Engineering & Python Development Project*

**Areas of Interest:** Electrical Engineering · Computer Networking · RF Engineering · Python Development · Wireless Communication
