## vec directory

Used to store:

- `xxxxxx.vec` — DataVer, Parameter, Data Frame configuration files for ARINC 573 / ARINC 717 PCM  
- `aircraft.air` — aircraft configuration file  

Both `vec` and `air` files come from the AGS software.

Example:

<img src="https://github.com/osnosn/FlightDataDecode/raw/main/wgl/vec/readme01.png" width="300" />

---

AirFASE can export four types of files: FAP, Frame, PRM, FRED.

- **FAP** and **Frame** are encrypted. They cannot be decoded.  
- **PRM** is a text file. Its structure is different from the format used here. The decoding logic is similar, but this program cannot use PRM directly. You can write your own parser if needed.  
  See also: [osnosn/FlightDataDecode2](https://github.com/osnosn/FlightDataDecode2/)  
- **FRED** is undocumented. Content unknown.

Other AirFASE screens:

<img src="https://github.com/osnosn/FlightDataDecode/raw/main/wgl/vec/airfase-app.jpg" width="300" />

<img src="https://github.com/osnosn/FlightDataDecode/raw/main/wgl/vec/airfase-FAP.png" width="500" />

<img src="https://github.com/osnosn/FlightDataDecode/raw/main/wgl/vec/airfase-Frame.png" width="300" />

<img src="https://github.com/osnosn/FlightDataDecode/raw/main/wgl/vec/airfase-PRM-header.png" width="300" />

<img src="https://github.com/osnosn/FlightDataDecode/raw/main/wgl/vec/airfase-regular.png" width="500" />

<img src="https://github.com/osnosn/FlightDataDecode/raw/main/wgl/vec/airfase-superframe.png" width="500" />
