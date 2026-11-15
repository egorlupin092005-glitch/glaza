# Тестовое изображение

`hand_sample.jpg` — тестовое изображение из официального примера MediaPipe:
https://storage.googleapis.com/mediapipe-tasks/hand_landmarker/woman_hands.jpg

Пример, ссылающийся на него:
https://github.com/google-ai-edge/mediapipe-samples/blob/main/examples/hand_landmarker/python/hand_landmarker.ipynb

Изображение используется только для проверки распознавания, не является кадром пользователя или записью работы его стенда.

Полная проверка программного цикла без оборудования:
`.venv\Scripts\python.exe tests\smoke_pipeline.py`

Камера и последовательный порт в этой проверке подменены тестовыми объектами; модель распознавания, обработка кадров, расчёт углов и протокол используются настоящие.
