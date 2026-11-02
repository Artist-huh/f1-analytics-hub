Pod::Spec.new do |s|
  s.name             = 'flet_radio'
  s.version          = '0.1.0'
  s.summary          = 'Радио команд F1 Analytics Hub: декодер mp3 (miniaudio) для расшифровки на iPhone.'
  s.description      = 'Декодирует запись радио в моно 16 кГц для whisper.cpp; расшифровка и перевод — в Dart.'
  s.homepage         = 'https://github.com/Artist-huh/f1-analytics-hub'
  s.license          = { :type => 'MIT' }
  s.author           = { 'F1 Analytics Hub' => 'noreply@example.com' }
  s.source           = { :path => '.' }
  s.source_files     = 'Classes/**/*'
  s.dependency 'Flutter'
  s.platform         = :ios, '14.0'
  s.pod_target_xcconfig = { 'DEFINES_MODULE' => 'YES', 'EXCLUDED_ARCHS[sdk=iphonesimulator*]' => 'i386' }
  s.swift_version    = '5.0'
end
