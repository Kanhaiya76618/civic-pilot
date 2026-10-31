Add-Type -AssemblyName System.Speech
$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer
$outDir = "C:\Users\admin\.gemini\antigravity\scratch\civic-triage-system\data\ai_datasets\audio_samples"

$synth.SetOutputToWaveFile("$outDir\voice_pothole_accident_hazard.wav")
$synth.Speak("Urgent attention required. There is a deep dangerous pothole on Hosur Road right in front of the school. Two motorcyclists met with an accident this morning. It needs immediate barricading and emergency asphalt patching.")

$synth.SetOutputToWaveFile("$outDir\voice_water_main_rupture.wav")
$synth.Speak("Hello control room. A major underground water pipe has burst on 100 Feet Road, Indiranagar near the metro station. High pressure water is flooding the street and washing away the road foundation. Please shut the main valve immediately.")

$synth.SetOutputToWaveFile("$outDir\voice_garbage_overflow.wav")
$synth.Speak("Hi, the municipal waste truck has not cleared 5th Cross Koramangala for five days. Commercial trash and open food waste are overflowing onto the road causing heavy stench and public health risk.")

$synth.Dispose()
Write-Host "Audio generation finished!"
