PYTHON_COURSE = {
    "title": "🐍 Python Eğitimi",
    "description": "Sıfırdan profesyonel Python programlamaya kapsamlı eğitim.",
    "lessons": [
        {
            "title": "1. Python Nedir? İlk Programımız",
            "level": "Başlangıç",
            "content": """
Python, öğrenmesi kolay ve güçlü bir programlama dilidir.

Python ile web siteleri, masaüstü uygulamaları,
otomasyon araçları, veri analizleri ve yapay zekâ
uygulamaları geliştirebilirsin.

Python'un en önemli avantajlarından biri,
kodlarının okunmasının kolay olmasıdır.

Örneğin ekrana bir yazı yazdırmak için print()
komutunu kullanırız.

print() komutu Python'un en temel komutlarından biridir.

İlk programımızı yazalım:

print("Merhaba DEADY ACADEMY!")

Bu kod çalıştırıldığında ekranda şu yazı görünür:

Merhaba DEADY ACADEMY!

Python'da metinler genellikle tırnak işaretleri
içerisinde yazılır.

Tek tırnak veya çift tırnak kullanabilirsin.
Ancak açtığın tırnak türünü doğru kapatmalısın.

Python büyük ve küçük harflere duyarlıdır.
Örneğin print ile Print aynı şey değildir.

Bir Python programı yazarken kodları yukarıdan
aşağıya doğru çalıştırırız.
""",
            "code": 'print("Merhaba DEADY ACADEMY!")\nprint("Python öğreniyorum.")\nprint("İlk programımı yazdım!")',
            "explanation": """
1. satır ekrana Merhaba DEADY ACADEMY! yazar.
2. satır ekrana Python öğreniyorum. yazar.
3. satır ekrana İlk programımı yazdım! yazar.

Her print() komutu ayrı bir satırda çıktı üretir.
""",
            "exercise": """
Kendi ilk programını oluştur.

1. Ekrana kendi kullanıcı adını yazdır.
2. Ekrana yaşını yazdır.
3. Ekrana Python öğreniyorum yazdır.
4. Dört farklı print() komutu kullan.
""",
            "quiz": [
                {
                    "question": "Python'da ekrana yazı yazdırmak için hangi komut kullanılır?",
                    "options": ["input()", "print()", "write()", "show()"],
                    "answer": 1
                },
                {
                    "question": "Python büyük ve küçük harfe duyarlı mıdır?",
                    "options": ["Evet", "Hayır"],
                    "answer": 0
                }
            ]
        },
        {
            "title": "2. Değişkenler ve Veri Türleri",
            "level": "Başlangıç",
            "content": """
Değişkenler, program içerisinde bilgi saklamamızı
sağlayan isimlendirilmiş alanlardır.

Bir kutunun içine eşya koyduğunu düşün.
Değişkenler de bilgisayarın belleğinde değer
saklamak için kullandığımız kutular gibidir.

Örneğin:

isim = "Enes"
yas = 20

Burada isim değişkeninde Enes metni,
yas değişkeninde ise 20 sayısı saklanır.

Python'da değişken oluştururken önceden
bir veri türü belirtmemiz gerekmez.

Python, verilen değere bakarak türü kendisi belirler.

Temel veri türleri:

str: Metinleri saklar.
int: Tam sayıları saklar.
float: Ondalıklı sayıları saklar.
bool: Doğru veya yanlış değerlerini saklar.

Örnek:

isim = "Enes"
yas = 20
boy = 1.75
ogrenci_mi = True

Değişkenlerin değerlerini type() komutuyla
kontrol edebiliriz.

Değişken isimleri boşluk içeremez.
İsimlendirmelerde alt çizgi kullanabilirsin.

Örneğin kullanici_adi geçerli bir isimdir.
""",
            "code": 'isim = "Enes"\nyas = 20\nboy = 1.75\naktif = True\n\nprint(isim)\nprint(yas)\nprint(type(isim))\nprint(type(yas))\nprint(type(boy))\nprint(type(aktif))',
            "explanation": """
isim bir metin değişkenidir.
yas bir tam sayı değişkenidir.
boy bir ondalıklı sayı değişkenidir.
aktif bir mantıksal değişkendir.

type() değişkenin veri türünü gösterir.
""",
            "exercise": """
Bir öğrenci bilgi programı oluştur.

1. ogrenci_adi değişkeni oluştur.
2. ogrenci_yasi değişkeni oluştur.
3. not_ortalamasi değişkeni oluştur.
4. kayitli_mi değişkenini True yap.
5. Tüm değişkenleri ekrana yazdır.
6. type() ile veri türlerini kontrol et.
""",
            "quiz": [
                {
                    "question": "Metin veri türünün adı nedir?",
                    "options": ["int", "float", "str", "bool"],
                    "answer": 2
                },
                {
                    "question": "20.5 sayısının türü hangisidir?",
                    "options": ["int", "float", "str", "bool"],
                    "answer": 1
                }
            ]
        },
        {
            "title": "3. Matematiksel İşlemler ve Operatörler",
            "level": "Başlangıç",
            "content": """
Python yalnızca yazı yazdırmak için kullanılmaz.
Matematiksel işlemler de yapabiliriz.

Temel matematik operatörleri:

+ Toplama
- Çıkarma
* Çarpma
/ Bölme
// Tam sayı bölmesi
% Mod alma
** Üs alma

Örnek:

a = 10
b = 3

print(a + b)

Sonuç 13 olur.

Bölme işleminde / kullanırsak ondalıklı sonuç
elde edebiliriz.

10 / 3 sonucu yaklaşık 3.333 olur.

10 // 3 işleminin sonucu 3'tür.

Mod alma operatörü % ise bölümden kalanı verir.
10 % 3 işleminin sonucu 1 olur.

Üs alma için ** kullanılır.
2 ** 3 işleminin sonucu 8'dir.

Bu operatörler hesap makineleri, puan sistemleri,
oyunlar ve finans uygulamalarında kullanılabilir.
""",
            "code": 'a = 10\nb = 3\n\nprint("Toplama:", a + b)\nprint("Çıkarma:", a - b)\nprint("Çarpma:", a * b)\nprint("Bölme:", a / b)\nprint("Tam bölme:", a // b)\nprint("Kalan:", a % b)\nprint("Üs:", a ** b)',
            "explanation": """
Her print() satırı farklı bir matematik işlemi yapar.

a ve b değişkenleri işlem yapılacak sayıları tutar.
Python işlem sonucunu hesaplayıp ekrana yazdırır.
""",
            "exercise": """
Basit bir hesap makinesi oluştur.

1. İki sayı belirle.
2. Toplamlarını hesapla.
3. Farklarını hesapla.
4. Çarpımlarını hesapla.
5. Bölümlerini hesapla.
6. Sonuçları açıklayıcı yazılarla ekrana yazdır.
""",
            "quiz": [
                {
                    "question": "Python'da üs alma operatörü hangisidir?",
                    "options": ["*", "**", "//", "%"],
                    "answer": 1
                },
                {
                    "question": "10 % 3 işleminin sonucu nedir?",
                    "options": ["3", "10", "1", "0"],
                    "answer": 2
                }
            ]
        },
        {
            "title": "4. Koşullar: if, elif ve else",
            "level": "Başlangıç",
            "content": """
Programlarımızın bazen karar vermesi gerekir.

Örneğin bir kullanıcının yaşına göre giriş izni
vermek isteyebiliriz.

Bunun için koşul ifadelerini kullanırız.

if kelimesi eğer anlamına gelir.

else ise yukarıdaki koşullar doğru değilse
çalıştırılacak kodları belirtir.

elif birden fazla koşulu kontrol etmemizi sağlar.

Örnek:

yas = 18

if yas >= 18:
    print("Giriş serbest")
else:
    print("Giriş yasak")

Burada yaş 18 veya daha büyükse ilk mesaj yazılır.

Koşul doğru değilse else bloğu çalışır.

Python'da girintiler çok önemlidir.
if ve else içerisindeki kodlar genellikle
dört boşluk içeriden yazılır.

Karşılaştırma operatörleri:

== Eşit mi?
!= Eşit değil mi?
> Büyük mü?
< Küçük mü?
>= Büyük veya eşit mi?
<= Küçük veya eşit mi?

Tek bir eşittir (=) değer atar.
İki eşittir (==) karşılaştırma yapar.
""",
            "code": 'yas = 20\n\nif yas >= 18:\n    print("Yetişkin")\nelif yas >= 13:\n    print("Genç")\nelse:\n    print("Çocuk")',
            "explanation": """
Python önce yas >= 18 koşulunu kontrol eder.

Doğruysa Yetişkin yazar ve diğer koşulları
kontrol etmez.

İlk koşul yanlışsa elif kontrol edilir.

O da yanlışsa else bloğu çalışır.
""",
            "exercise": """
Bir not değerlendirme programı oluştur.

1. not isimli bir değişken oluştur.
2. Not 85 veya üzeriyse Çok iyi yaz.
3. Not 70 veya üzeriyse İyi yaz.
4. Not 50 veya üzeriyse Geçti yaz.
5. Diğer durumlarda Kaldı yaz.
""",
            "quiz": [
                {
                    "question": "Python'da koşul oluşturmak için hangisi kullanılır?",
                    "options": ["for", "if", "def", "import"],
                    "answer": 1
                },
                {
                    "question": "İki değerin eşitliğini hangi operatör kontrol eder?",
                    "options": ["=", "==", "!=", ">"],
                    "answer": 1
                }
            ]
        },
        {
            "title": "5. Döngüler: for ve while",
            "level": "Başlangıç",
            "content": """
Döngüler, aynı işlemi tekrar tekrar yapmamızı sağlar.

Örneğin ekrana 1'den 100'e kadar sayıları yazdırmak
istediğini düşün.

Her sayı için ayrı print() yazmak yerine döngü
kullanabiliriz.

Python'da en çok kullanılan iki döngü türü
for ve while döngüleridir.

FOR DÖNGÜSÜ

for döngüsü genellikle kaç kez tekrar yapılacağını
bildiğimiz durumlarda kullanılır.

Örnek:

for sayi in range(5):
    print(sayi)

range(5), 0'dan başlayarak 5'e kadar sayılar üretir.
Son değer olan 5 dahil değildir.

WHILE DÖNGÜSÜ

while döngüsü verilen koşul doğru olduğu sürece
çalışmaya devam eder.

Örnek:

sayi = 1

while sayi <= 5:
    print(sayi)
    sayi += 1

sayi += 1 ifadesi sayıyı bir artırır.

Dikkat: while döngüsünde koşul hiçbir zaman
yanlış olmazsa sonsuz döngü oluşabilir.

Bu nedenle döngünün durmasını sağlayacak
bir koşul hazırlamak önemlidir.

Döngüler oyunlarda, listelerde, otomasyonlarda
ve tekrar eden işlemlerde çok kullanılır.
""",
            "code": 'for sayi in range(1, 6):\n    print("Sayı:", sayi)\n\nprint("While örneği")\n\nsayac = 1\nwhile sayac <= 5:\n    print("Sayaç:", sayac)\n    sayac += 1',
            "explanation": """
İlk döngü 1, 2, 3, 4 ve 5 sayılarını yazdırır.

İkinci döngü sayac değişkenini kullanır.

Her tekrar sonunda sayac bir artırılır.
Sayaç 5'i geçtiğinde while koşulu yanlış olur
ve döngü sona erer.
""",
            "exercise": """
Bir sayı sayma programı oluştur.

1. for ile 1'den 20'ye kadar say.
2. while ile 10'dan 1'e kadar geri say.
3. 1 ile 50 arasındaki çift sayıları yazdır.
4. Her sayının karesini hesapla.
""",
            "quiz": [
                {
                    "question": "Belirli bir sayı aralığında tekrar için hangisi kullanılır?",
                    "options": ["for", "if", "def", "class"],
                    "answer": 0
                },
                {
                    "question": "while döngüsü ne zaman çalışır?",
                    "options": [
                        "Koşul doğru olduğu sürece",
                        "Her zaman yalnızca bir kez",
                        "Yalnızca hata olunca",
                        "Program kapanınca"
                    ],
                    "answer": 0
                }
            ]
        }
    ]
}
