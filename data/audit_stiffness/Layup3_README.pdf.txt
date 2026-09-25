PAGE 1
Data Description: 
The data reported in this document correspond to the test of fatigue aging on CFRP composites carry out by the Stanford 
Structures and Composites Laboratory (SACL) in collaboration with the Prognostic Center of Excellence (PCoE) of NASA Ames 
Research Center. In this experiment, a set of coupons were subject to a tension-tension fatigue test conducted under a load 
controlled loop of cyclical loadings with a frequency of 5.0 [Hz] and a stress ratio of R ~ 0.14. The coupons were laminated with 
three symmetric layup configurations to account for the effect of ply orientation: 
a ) Layup 1: [02/904]s;  
b ) Layup 2: [0/902/45/−45/90]s; and  
c ) Layup 3: [902/45/−45]2s. 
Torayca T700G unidirectional carbon-prepreg material was used for 15.24 [cm] × 25.4 [cm] coupons with dogbone geometry. A 
notch (5.08 [mm] × 19.3 [mm]) to induce stress concentration was created in these coupons. Fatigue damage was monitored by 
two sets of six-PZT-sensor SMART Layer® from Acellent Technologies, Inc. The sensors were attached to the surface of each 
sample. This configuration allows six actuators and six sensors to monitor Lamb wave propagation through the samples (see 
Figure 1). Each of the 36 actuator-sensor trajectories were actuated at 7 different interrogation frequencies in the range of 
150−450 [KHz], with an average input voltage of 50 volts and a gain of 20dB.  
All tests were performed on an MTS machine following ASTM Standards D3039 and D3479 [1, 2]. The fatigue cycling tests 
were stopped every fixed number of cycles (normally 50,000 cycles) to collect PZT sensor data for all trajectories and 
interrogation frequencies. X-rays of the samples were taken using a dye-penetrant to enhance X-ray absorption. See further 
details in [3]. For further details about using this dataset for prognostics and predicting fatigue in composites, please refer to 
publications [4] and [5].  
Data Set Files 
At the top level dataset is organized into three zipped files each corresponding to one layup type as described below. 
Layup1.zip: L1S11,L1S12,L1S17,L1S18,L1S19. 
Layup2.zip: L2S11,L2S12,L2S17,L2S18,L2S20. 
Layup3.zip: L3S11,L3S13,L3S14,L3S20.  
In addition to individual folders containing test data for respective coupon ID, there is a readme.pdf file that explains the overall 
data structure, basic experiment information, and cites reports and papers that will useful in many questions that users may have. 
Also, included is a Documentation folder with all cited reports and publications. 
Data Folder Contents (labeled as LayupID_CouponID_TestType, e.g. L1_S11_F): 
a. LogBook Excel® Spreadsheet -This spreadsheet describes data collection and experiment log with operator 
observations. 
b. PZT-data-This folder contains Matlab® files with PZT signal information. 
c. StrainData-This folder contains the files for the strain data collected from:  
i. The strain-gauge sensors attached on the coupon and/or  
ii. MTS machine raw dataset. 
d. XRay- This is a folder containing a set of XRay images which were taken at regular intervals to visualize damage and 
establish ground truth information.. 
------------------------------------------------------------------------------------------------------------------------------------------------------------
It is IMPORTANT TO KNOW that there are several laminates where the strain data are not available from strain-gauge sensors. 
In these cases, only the MTS machine files are provided. See below the list of coupons without strain-gauge information: 
L1S17,L1S18,L2S18,L2S17,L2S20,L3S18,L3S20. 
In addition, please note following differences in data for some coupons: 
1) Coupons L1S18, L1S17 contain pictures of the Xray film. 
2) Coupons L3S13, L3S14 do not contain available Xray images, but a hand-traced drawing of the Xrays.  
------------------------------------------------------------------------------------------------------------------------------------------------------------ 
 

PAGE 2
Data Structure: 
 
coupon: top level structure array containing: cycle, load, XRay_data, Straingage_data, and condition. 
 
 #cycle.-This is the cycle value corresponding to the measurement. 
 #load.-Load value in [Kips] applied to the coupon while the measurement. 
 #condition.- This variable can have three values: Loaded, Clamped (0 load but clamped), and Traction 
Free (absolutely 0 loads).  
 #XRay_data.- 
  @file_location: the name of the Xray file which is located on the XRay folder. 
 #Straingage_data.- 
  @file_location:the name of the strain data file which is located on the StrainData folder. 
  @stiffness_degradation: stiffness value obtained from the strain-gages. 
 #path data.- 
  path.data(i,j) 
   @actuator: actuator number ID. See the scheme below. 
   @sensor: sensor number ID. See the scheme below. 
   @amplitude: signal amplitude. 
   @sampling_rate: [Hz] 
   @frequency: signal frequency. 
   @gain: voltage value, to increase the signal features. 
   @signal_actuator: array defining the signal from the actuator "@actuator". 
   @signal_sensor: array defining the received signal from the sensor "@sensor" 
    
PZT Sensors and Actuators placement: 
 
In this experiment, we use 6 actuators which act as Lamb-wave precursors; and 6 sensors, acting as wave-receivers. To increase 
the likelihood of detecting the damage, all the actuators are connected to all the sensors defining a total number of 36 propagation 
trajectories. Each trajectory is actuated at 7 different frequencies, obtaining a total of 252 paths.  
For more information, please contact:  
Abhinav Saxena, Kai Goebel: {abhinav.saxena, kai.goebel}@nasa.gov 
Manuel Chiachio Ruano, Juan Chiachio Ruano: {mchiachio, jchiachio}@ugr.es 
Acknowledgements: 
Authors would like to thank the Structures and Composites lab at Stanford University for experimental data and NASA 
ARMD/AvSafe project SSAT, which provided partial support for this experimental work. 
References: 
[1] ASTM, Standard Test Method for Tension-Tension Fatigue of Polymer Matrix Composite Materials, in D3479/D3479M 96. 
ASTM International, 2007. 
[2] ASTM, Standard Test Method for Tensile Properties of Polymer Matrix Composite Materials, in D3039/D3039M 08. ASTM 
International, 2008. 
[3] Abhinav Saxena, Kai Goebel, Cecilia C. Larrosa, Vishnuvardhan Janapati, Surajit Roy, and Fu-Kuo Chang. Accelerated 
aging experiments for prognostics of damage growth in composite materials. Proceedings of the 8th International Workshop on 
Structural Heath Monitoring 2011, (Stanford Univ.), Destech Publications Inc. 
[4] M. Chiachio, J. Chiachio, A. Saxena, G.Rus, K.Goebel, Fatigue damage prognosis in FRP composites by combining multi-
scale degradation fault modes in an uncertainty Bayesian framework, Proceedings of the 9th International Workshop on 
Structural Heath Monitoring 2013, (Stanford Univ.), Destech Publications Inc. 


PAGE 3
[5] Juan Chiachio, Manuel Chiachio, Abhinav Saxena, Guillermo Rus, Kai Goebel,An Energy-Based Prognostic Framework to 
Predict Fatigue Damage Evolution in Composites. Proceedings of Annual Conference of the Prognostics and Health Management 
Society, 2013. (http://www.phmsociety.org/node/1073) 
 
 
 