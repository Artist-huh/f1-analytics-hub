# Декодер записей радио для Android (на iPhone тот же файл собирает CocoaPods, см. ios/flet_radio.podspec)
cmake_minimum_required(VERSION 3.10)
project(flet_radio LANGUAGES C)

add_library(flet_radio SHARED radio_decode.c)
set_target_properties(flet_radio PROPERTIES OUTPUT_NAME "flet_radio")
target_compile_options(flet_radio PRIVATE -O2)
if(ANDROID)
  # Android 15+: страницы памяти 16 КБ — библиотеки должны быть выровнены
  target_link_options(flet_radio PRIVATE "-Wl,-z,max-page-size=16384")
  target_link_libraries(flet_radio PRIVATE m)
endif()
