# Guion de la presentación — Alerta temprana de puntos de quiebre

Sistemas Complejos · Universidad EIA · 3 de noviembre de 2026 · Fernando

## Cómo usar este guion

Este archivo tiene tres partes. La primera son los 15 slides con el texto que vas a decir, palabra por palabra, más lo que se ve en pantalla, la transición al siguiente slide y qué cortar si vas tarde. La segunda son los respaldos (B1 a B6), que solo abres si alguien pregunta. La tercera son los extras: glosario, qué no afirmar, plan B, preguntas difíciles, números para memorizar, referencias y la lista del día de la presentación. Lo que está en **Decir:** es para leerlo en voz alta casi tal cual, pero no lo memorices como poema: aprende la idea de cada párrafo y usa el texto como red de seguridad. Lo que va entre corchetes, como [pausa] o [▶ clic], es una instrucción para ti y no se dice. Los números salen todos de `results/key_numbers.json` (y los de B6 de `results/confound.json`), y en el texto van con coma decimal como se escribe en español; al decirlos, lee "cero coma tres ocho cinco". El ritmo objetivo es de 140 a 150 palabras por minuto; si te pasas de 150 estás corriendo. En los tres videos (A1, A2, A3) puedes callarte: el silencio mientras algo se mueve es parte de la charla. Ajusta cualquier frase sobre el curso (por ejemplo, la mención del caos en el slide 2) a lo que realmente se vio en clase.

### Tiempo por slide

| Slide | Tema | Tiempo | Acumulado | Palabras |
| --- | --- | --- | --- | --- |
| 1 | Hook | 0:30 | 0:30 | 70 |
| 2 | Idea y meta | 1:00 | 1:30 | 137 |
| 3 | ¿Qué es un punto de quiebre? | 1:00 | 2:30 | 146 |
| 4 | Modelo: una bola en valles | 1:15 | 3:45 | 191 |
| 5 | Equilibrios y diagrama de bifurcación | 1:00 | 4:45 | 159 |
| 6 | Animación A1: la bifurcación | 1:30 | 6:15 | 125 |
| 7 | Histéresis | 1:00 | 7:15 | 137 |
| 8 | Física estocástica | 1:15 | 8:30 | 161 |
| 9 | Animación A2: la bola con ruido | 1:00 | 9:30 | 146 |
| 10 | La señal: varianza y AR(1) | 1:30 | 11:00 | 205 |
| 11 | El experimento | 1:00 | 12:00 | 144 |
| 12 | Resultados y animación A3 | 1:15 | 13:15 | 162 |
| 13 | ¿Por qué un control? | 1:00 | 14:15 | 132 |
| 14 | ¿Cuándo falla? | 2:00 | 16:15 | 295 |
| 15 | Qué nos dice y por qué importa | 1:30 | 17:45 | 214 |

Total hablado: 2424 palabras, unos 16.7 minutos a 145 palabras por minuto, más unos 40 segundos de silencio durante los tres videos; en total, cerca de 17:20 de los 17:45 disponibles. Si el ensayo te sale por encima de 17:45, usa los recortes de la sección Plan B.

Puntos de control para saber si vas bien: al terminar el slide 5 deberías estar cerca de 4:45; al terminar el slide 10, cerca de 11:00; al empezar el slide 14, cerca de 14:15. Si en el slide 10 vas más allá de 12:00, aplica los recortes de la sección Plan B.

### Los 5 mensajes que no puedes olvidar

1. Un punto de quiebre por bifurcación silla-nodo tiene un aviso físico: la tasa de recuperación λ se acerca a cero y el sistema se vuelve lento (desaceleración crítica).
2. Ese aviso se puede medir en una serie de tiempo ruidosa, sin conocer el modelo: sube la varianza y sube la autocorrelación.
3. Sin un grupo de control no sabes si un aumento es alarma o azar: las series con memoria fabrican tendencias.
4. En condiciones favorables la señal casi separa perfecto (AUC cercano a 1), pero solo si se mira hasta cerca del pliegue, y falla cuando la rampa es corta o cuando el ruido es tan grande que el sistema cae solo, antes del pliegue.
5. La señal dice "nos estamos acercando", no "cae el día tal"; es un modelo de juguete con datos simulados y no demuestra que funcione en el clima.

---

## Slide 1 — Hook

**Tiempo:** 0:30 (acumulado 0:30)

**En pantalla:** una serie de tiempo ruidosa, sin ejes ni texto, que baja muy despacio y de repente cae a un nivel mucho más bajo.

**Decir:**

Miren esta serie de tiempo. Durante mucho rato casi no pasa nada: baja despacito, con un poco de ruido. [pausa] Y de repente, cae.

Ahora imaginen que yo les hubiera mostrado solo la parte de la izquierda. ¿Habrían podido adivinar que venía esa caída? Esa es la pregunta de hoy: ¿un sistema avisa antes de llegar a su punto de quiebre?

**Transición:** Para responderla, primero les cuento qué idea voy a probar.

**Si te quedas sin tiempo:** nada que cortar; es el slide más corto.

---

## Slide 2 — Idea y meta

**Tiempo:** 1:00 (acumulado 1:30)

**En pantalla:** la idea en una frase y la meta del proyecto (pregunta, método, qué se mide). Título sugerido: "Queremos ver el punto de quiebre antes de que ocurra". Ajusta el guion si el texto del slide dice otra cosa.

**Decir:**

Hola a todos, soy Fernando. Muchos sistemas aguantan estables durante años y luego saltan de golpe a otro estado: un lago que pasa de agua clara a turbia, un ecosistema, y también se discuten componentes del clima. Ustedes ya vieron algo de caos en el curso; hoy es otra cara de los sistemas complejos: un sistema muy simple que cambia bruscamente, y la pregunta es si se puede ver venir.

La idea es esta. Si el salto es una bifurcación y el parámetro se acerca despacio, el sistema debería mostrar síntomas antes de saltar, y esos síntomas se pueden medir en una serie de tiempo. Mi meta fue comprobarlo en un modelo donde yo conozco la verdad exacta, con un grupo de control, y encontrar en qué condiciones falla.

**Transición:** Para eso necesito primero ponerle nombre al fenómeno.

**Si te quedas sin tiempo:** corta la mención del caos y los ejemplos; deja la idea y la meta.

---

## Slide 3 — ¿Qué es un punto de quiebre?

**Tiempo:** 1:00 (acumulado 2:30)

**En pantalla:** definición de punto de quiebre y los tres tipos (por bifurcación, por ruido, por tasa).

**Decir:**

Un punto de quiebre es cuando un cambio pequeño y lento en una condición externa, que llamaremos parámetro de control, produce un cambio grande y brusco en el estado del sistema, y además difícil de revertir. [pausa]

En la literatura se distinguen tres rutas; esa clasificación aparece en Ashwin y colaboradores, de 2012. Una: por bifurcación, el parámetro cruza un valor crítico y el estado estable simplemente desaparece. Dos: por ruido, las fluctuaciones empujan al sistema por encima de una barrera aunque el parámetro todavía esté en la zona segura. Tres: por tasa, el parámetro cambia tan rápido que el sistema no alcanza a seguirlo.

Hoy me concentro en la primera, la bifurcación, que es la que tiene una señal de aviso bien entendida. Pero, ya lo van a ver, el ruido se mete en la historia.

**Transición:** Veamos la bifurcación en el modelo más simple que conozco.

**Si te quedas sin tiempo:** deja solo la definición y la frase "hoy me concentro en la bifurcación"; salta la lista de los tres tipos.

---

## Slide 4 — Modelo: una bola en valles

**Tiempo:** 1:15 (acumulado 3:45)

**En pantalla:** tres paisajes de potencial, para r = 0, r = −0,2 y r = −0,385, con una bola en el valle de la derecha. Puntos azules: equilibrios estables. Círculo naranja: el inestable. Rombo gris: el pliegue.

**Decir:**

Uso el modelo más simple que tiene esta física: una bola que se mueve en un paisaje. La ecuación es dx sobre dt igual a r más x menos x al cubo. Esa fuerza es menos la derivada de un potencial V, así que la bola siempre baja por la pendiente. Y es sobreamortiguada: no hay inercia, la bola no se pasa de largo, solo se desliza hasta un fondo y se queda. Por eso, en una dimensión no hay oscilaciones.

Miren los tres paisajes. Con r igual a cero hay dos valles simétricos y la bola está en el de la derecha. Los puntos azules son equilibrios estables; el círculo naranja es el equilibrio inestable, la cima entre los valles. El parámetro r inclina el paisaje, como inclinar una mesa. Con r igual a menos 0,2, el valle derecho ya es más somero. Y con r igual a menos 0,385 el valle derecho desaparece: queda un hombro plano, el rombo gris, y la bola no tiene dónde quedarse. Tiene que caer al valle de la izquierda.

**Transición:** Pasemos esto del paisaje a un diagrama de todos los equilibrios a la vez.

**Si te quedas sin tiempo:** corta la explicación de "sobreamortiguada" y la imagen de la mesa.

---

## Slide 5 — Equilibrios y diagrama de bifurcación

**Tiempo:** 1:00 (acumulado 4:45)

**En pantalla:** diagrama de bifurcación: rama azul sólida (estable), rama naranja punteada (inestable), zona sombreada "biestable", dos rombos grises en r = ±0,385, flecha violeta "r disminuye". Fórmulas: λ(x) = 1 − 3x² y r_c = 2/(3√3) ≈ 0,385.

**Decir:**

Los equilibrios son las soluciones de r más x menos x al cubo igual a cero: una cúbica. Tiene tres raíces reales cuando el valor absoluto de r es menor que r crítico, dos sobre tres raíz de tres, más o menos 0,385.

¿Cuáles son estables? Lo dice λ de x, igual a uno menos tres x al cuadrado: la derivada de la fuerza en el equilibrio, o sea, la tasa con la que crece o decae una perturbación pequeña, como e a la λ por t. Si λ es negativa, decae y el equilibrio es estable.

En el diagrama, la línea azul es estable y la naranja punteada, inestable. Hacemos bajar r, la flecha violeta. En menos 0,385, la rama estable de arriba choca con la inestable y las dos se aniquilan. Justo ahí λ vale cero. Eso es una bifurcación silla-nodo, o pliegue, y el salto que sigue mide raíz de tres, cerca de 1,7.

**Transición:** Veámoslo moviéndose.

**Si te quedas sin tiempo:** no expliques de dónde sale r crítico; di solo "alrededor de 0,385" y quédate con "λ vale cero en el pliegue".

---

## Slide 6 — Animación A1: la bifurcación

**Tiempo:** 1:30 (acumulado 6:15)

**En pantalla:** a la izquierda el paisaje de potencial con la bola; a la derecha el diagrama de bifurcación con un marcador que sigue a la bola. Video de 16 s. Poster: r = −0,37, "El valle derecho se aplana y desaparece".

**Animación:** dale play justo después de decir "Fíjense en cómo se va aplanando el valle de la derecha." Dura 16 s; r baja despacio de 0,3 a −0,6. Mientras corre, no hables salvo por un cue: cuando el marcador cruce la línea punteada vertical (r = −0,385), di en voz baja "ahí". Cuando termine, la bola ya está en el valle de la izquierda.

**Decir:**

Ahora en movimiento. A la izquierda, el paisaje; a la derecha, el diagrama, con un marcador que muestra dónde está la bola. Voy a hacer bajar r despacio, de 0,3 a menos 0,6. Fíjense en cómo se va aplanando el valle de la derecha. [▶ clic: reproducir; callarse ~16 s; en voz baja "ahí" cuando el marcador pase la línea punteada]

Cayó. Y noten que cae un poquito después de la línea punteada: cuando el valle está casi plano, la bola reacciona cada vez más lento. Eso es lo importante. Un sistema real no me da el paisaje, solo me da la serie de x contra tiempo. Pero ese aplanamiento, λ tendiendo a cero, debería dejar una huella en cómo se mueve la bola. Para verla necesito ruido.

**Transición:** Primero, una consecuencia de esta geometría que no se puede dejar pasar: la histéresis.

**Si te quedas sin tiempo:** corta el "ahí" y la frase sobre la reacción lenta; di solo "cayó, y para ver el aviso necesito ruido".

---

## Slide 7 — Histéresis

**Tiempo:** 1:00 (acumulado 7:15)

**En pantalla:** el mismo diagrama, con flechas violetas: "r disminuye" arriba y salto hacia abajo en −0,385; "r aumenta" abajo y salto hacia arriba en +0,385; cota "ancho del lazo 2r_c ≈ 0,77".

**Decir:**

Sigan la flecha de arriba: bajamos r y la bola cae en menos 0,385. Ahora subamos r, la flecha de abajo: la bola no vuelve; recién salta hacia arriba en más 0,385. [pausa]

Los saltos ocurren en valores distintos de r, así que el estado depende de la historia, no solo del parámetro. En la zona entre los dos pliegues, que mide dos veces r crítico, unos 0,77, hay dos estados posibles, y cuál ocupa el sistema depende de por dónde vino. Es el mismo ciclo de un ferromagneto: aquí r hace de campo magnético y r crítico de campo coercitivo.

Consecuencia: tras un quiebre no basta devolver r; hay que pasarlo al otro lado. Por eso interesa avisar antes.

**Transición:** Hasta aquí todo es determinista. Ahora toca meter ruido, y para eso la física ya tiene una historia.

**Si te quedas sin tiempo:** corta la analogía magnética; deja "el estado depende de la historia" y "por eso interesa avisar antes".

---

## Slide 8 — Física estocástica

**Tiempo:** 1:15 (acumulado 8:30)

**En pantalla:** línea de tiempo Einstein 1905, Langevin 1908, Uhlenbeck–Ornstein 1930; la ecuación dx = f dt + σ dW; a la izquierda "sin ruido" (la bola cae a x* = 1 y se queda quieta) y a la derecha "con ruido, σ = 0,05" (fluctúa alrededor de x* = 1).

**Decir:**

Ningún sistema real está aislado: siempre hay perturbaciones, y esta historia la conocen los físicos. En 1905 Einstein explicó el movimiento browniano: una partícula en un líquido se mueve porque recibe choques aleatorios de las moléculas. En 1908 Langevin lo escribió como una ecuación de movimiento con una fuerza aleatoria. En 1930 Uhlenbeck y Ornstein estudiaron la velocidad de una partícula browniana con fricción, un proceso que se resuelve completo y que lleva hoy sus nombres; cerca del equilibrio, nuestra desviación es el mismo proceso.

En nuestra notación: dx igual a f dt más σ dW. W es el proceso de Wiener: incrementos independientes y gaussianos, con varianza igual al tiempo transcurrido; por eso en la simulación el ruido entra con raíz de dt.

Miren la figura. Sin ruido, la bola cae al equilibrio y se queda quieta; con σ igual a 0,05, se queda temblando alrededor de él.

**Transición:** Pongamos ese temblor en el modelo, mientras r baja hacia el pliegue.

**Si te quedas sin tiempo:** corta la explicación de la raíz de dt (queda en las preguntas) y reduce la historia a "Einstein, Langevin, Uhlenbeck y Ornstein".

---

## Slide 9 — Animación A2: la bola con ruido

**Tiempo:** 1:00 (acumulado 9:30)

**En pantalla:** arriba el paisaje con la bola; abajo la serie x(t), con la línea azul del equilibrio estable y la naranja punteada del inestable. Video de 14 s. Poster: r = −0,28, "Las fluctuaciones crecen y se vuelven más lentas". El pie de la figura debería decir "σ = 0,16 · corrida ilustrativa".

**Animación:** dale play al terminar "qué tan rápido se deshace cada empujón." Mientras corre, no hables. Hacia los últimos 3 segundos aparece una fluctuación grande de la serie (t ≈ 64) de la que se recupera: puedes señalarla con la mano. Al terminar, r llegó a −0,34, todavía antes del pliegue, y la bola sigue arriba.

**Decir:**

Ahora la bola con ruido, y r baja de cero a menos 0,34, todavía antes del pliegue. Ojo: esto es una ilustración, no el experimento. Para que se vea, aquí el ruido es mayor, σ igual a 0,16 en vez de 0,05; la rampa es unas 15 veces más rápida; y elegí una corrida que no cae. Con ese ruido, cae en el 21 % de los casos. Abajo está x contra tiempo, con el equilibrio estable en azul y el inestable en naranja. Miren el tamaño de las fluctuaciones y qué tan rápido se deshace cada empujón. [▶ clic: reproducir; callarse ~14 s]

Esta no cayó. Las fluctuaciones crecieron y se volvieron más lentas: el sistema tarda cada vez más en recuperarse de cada empujón. Eso es la desaceleración crítica, y ahí está la señal que buscamos.

**Transición:** Ahora hay que convertir esa impresión visual en dos números que se puedan calcular.

**Si te quedas sin tiempo:** corta la descripción de los colores de la serie; no cortes la advertencia de que es una ilustración con más ruido y una corrida elegida.

---

## Slide 10 — La señal: varianza y AR(1)

**Tiempo:** 1:30 (acumulado 11:00)

**En pantalla:** tres paneles. Izquierda: desviación del equilibrio en el tiempo (verde: valle empinado, r = 0, λ = −2,00; violeta: valle plano, r = −0,33, λ ≈ −0,68). Centro: distribución, más ancha la violeta. Derecha: autocorrelación; puntos de simulación y curvas punteadas de la teoría OU. Fórmulas: Var = σ²/(2|λ|) y ρ(Δt) = e^{λΔt}.

**Decir:**

¿Por qué ocurre, y cómo lo mido? Cerca de un equilibrio estable escribo la posición como el equilibrio más una desviación pequeña, y linealizo: me quedo solo con el término lineal. Queda dy igual a λ y dt más σ dW, con λ negativa. Es el proceso de Ornstein y Uhlenbeck, y se resuelve completo; les doy los resultados. La varianza vale σ al cuadrado sobre dos veces el valor absoluto de λ. La autocorrelación, a un retardo Δt, decae como e a la λ Δt. [pausa]

Cuando λ tiende a cero, la fuerza restauradora se debilita: la varianza sube y la memoria se alarga. Ambas se calculan desde la serie, sin conocer el modelo. A la autocorrelación a un paso la llamo AR(1).

La figura lo muestra. En verde, un valle empinado, λ igual a menos 2; en violeta, uno plano, λ cerca de menos 0,68. En el centro, la distribución violeta se ensancha; a la derecha, su autocorrelación decae más despacio. Puntos: simulación; líneas: teoría. Fíjense que los puntos violetas quedan un poco por encima de la curva: es la no linealidad, el valle plano no es un resorte perfecto. Eso está en el respaldo B1.

**Transición:** Con la señal definida, falta ponerla a prueba.

**Si te quedas sin tiempo:** corta la imagen de inyectar y sacar varianza y el nombre AR(1); deja las dos fórmulas, la figura y la frase sobre los puntos por encima de la curva.

---

## Slide 11 — El experimento

**Tiempo:** 1:00 (acumulado 12:00)

**En pantalla:** arriba, una corrida del grupo de rampa (r de 0 a −0,6) en violeta que cae; abajo, una corrida del control (r = 0) en verde, plana; una línea vertical punteada en el pliegue, con la etiqueta "pliegue (r = −r_c), t ≈ 1283,5" (no "punto de quiebre").

**Decir:**

Diseñé un experimento donde conozco la respuesta. Dos grupos de 300 simulaciones, con σ igual a 0,05. En la rampa, r baja linealmente de cero a menos 0,6 durante 2000 unidades de tiempo, y cruza el pliegue hacia t igual a 1283,5. En el control, r se queda en cero todo el tiempo.

Ojo: la rampa cae antes de la línea punteada, que marca el pliegue y no la caída. La mediana de caída es t igual a 1263, unas 20 unidades antes, y tres de cada cuatro corridas caen antes del pliegue. Sin ruido caería 28,5 unidades después, por el retardo de la bifurcación; el ruido la adelanta unas 49.

En cada serie quito la tendencia lenta, calculo varianza y AR(1) en una ventana de 200 unidades y mido con el tau de Kendall si suben.

**Transición:** Veamos qué sale, primero en una corrida.

**Si te quedas sin tiempo:** corta el párrafo de la ventana, el detrending y el tau (están en B3 y B4); no cortes que la rampa cae antes del pliegue.

---

## Slide 12 — Resultados y animación A3

**Tiempo:** 1:15 (acumulado 13:15)

**En pantalla:** el video A3 (19,5 s) y, junto a él, los números grandes: AUC con varianza (0,9998) y con AR(1) (0,995), y la tasa de detección con 5 % de falsas alarmas (1,00 con varianza y 0,99 con AR(1)). Título sugerido: "Las señales suben antes de la caída (si miro lo suficiente)". Ajusta el guion si el slide muestra otros números. Poster: arriba la serie de la rampa con una ventana violeta; en medio varianza (rampa violeta, control verde); abajo AR(1).

**Animación:** dale play al terminar "Miren cuándo se separan." Dura 19,5 s. Mientras corre, no hables durante los primeros 10 s. Cuando las curvas violetas ya se hayan separado claramente del verde (tras la mitad del video), di en voz baja la primera frase del párrafo de después. Al final la serie cae y la ventana se detiene.

**Decir:**

Esta es una sola corrida de la rampa. La ventana violeta se desliza hacia la derecha; en cada posición calculo varianza y AR(1) y los dibujo abajo, junto con la mediana del control, en verde. Miren cuándo se separan. [▶ clic: reproducir; callarse ~10 s]

[A mitad del video, cuando ya se separaron] La violeta sube mucho antes de la caída; la verde queda plana.

Pero una corrida no prueba nada; miramos las 300. El tau mediano de la rampa es 0,84 con varianza y 0,76 con AR(1); en el control, casi cero. El AUC es la probabilidad de que una corrida de rampa tenga tau mayor que una de control: 0,9998 con varianza y 0,995 con AR(1). Con 5 % de falsas alarmas permitidas, detecto el 100 % de las rampas con varianza y el 99 % con AR(1). Ojo: miré solo hasta el 60 % de la rampa, 83,5 unidades antes del pliegue, y eso lo elegí sabiendo dónde está el pliegue.

**Transición:** Pero esos números solo significan algo gracias al control. Veamos por qué.

**Si te quedas sin tiempo:** corta la frase "La violeta sube mucho antes..." y la definición del AUC; di solo "AUC 0,9998 y 0,995, y 99 a 100 % de detección con 5 % de falsas alarmas". No cortes el "miré solo hasta el 60 %".

---

## Slide 13 — ¿Por qué un control?

**Tiempo:** 1:00 (acumulado 14:15)

**En pantalla:** histograma del tau de Kendall del AR(1): control en verde (de −0,6 a cerca de 0,75, con muy pocas corridas por encima de 0,5), rampa en violeta (concentrada entre 0,6 y 0,9), línea punteada "umbral: 5 % de falsos positivos" y "AUC = 0,99".

**Decir:**

¿Por qué hace falta el control? Porque un tau de 0,3 no significa nada por sí solo. Estas series tienen memoria, y una serie con memoria produce tendencias aparentes aunque no cambie nada. Miren el control, en verde: sus taus van de menos 0,6 hasta cerca de 0,7, sin que el sistema haya cambiado. La línea punteada, en 0,47, deja solo el 5 % del control por encima, y la rampa, en violeta, queda casi toda a la derecha. Solo contra el control sé qué tan raro es un tau.

Una limitación honesta: con una serie real, una sola, no hay un control natural; habría que construirlo, con series sustitutas o con un periodo sin cambio. Aquí sí puedo, porque es simulación.

**Transición:** Ahora la pregunta que más me interesa: ¿cuándo falla esto?

**Si te quedas sin tiempo:** deja la idea "una serie con memoria fabrica tendencias" y la limitación de la serie real; corta la descripción del histograma.

---

## Slide 14 — ¿Cuándo falla?

**Tiempo:** 2:00 (acumulado 16:15)

**En pantalla:** dos mapas de calor del AUC, media de tres semillas, AR(1) a la izquierda y varianza a la derecha. Filas: ruido σ de 0,03 (abajo) a 0,30 (arriba). Columnas: duración de la rampa de 100 a 2000. Las celdas rayadas (σ = 0,30 con duraciones 400, 1000 y 2000, donde cae más del 20 % de los controles) son "el control cae solo".

**Decir:**

Esta es la parte que más me importa. Es el AUC, media de tres semillas: AR(1) a la izquierda, varianza a la derecha. Cada fila es un nivel de ruido, de 0,03 abajo a 0,30 arriba, y cada columna, la duración de la rampa. [pausa] Tres cosas.

Una. Abajo a la derecha, rampa larga y ruido bajo, el AUC es 1,00; 0,997 para el AR(1), media de tres semillas. Hacia la izquierda, con rampas cortas, baja hacia 0,6: con duración 100 y σ igual a 0,05, el AR(1) da 0,60. Lo comprobé aparte: con la misma ventana de 10 unidades, la rampa de 2000 da 0,94 y la de 100 da 0,61; con una ventana tres veces mayor, la rampa corta solo sube a 0,68. Manda la duración, no la ventana.

Dos. La fila de arriba, σ igual a 0,30. Las celdas rayadas son casos donde el control cae solo: con rampa de 2000, el 89 %. Ahí el AUC de 0,63 no se puede interpretar: solo sobreviven 112 de 300 rampas y 214 de 300 controles, y no son una muestra al azar.

Tres. Con σ igual a 0,15 y rampa de 2000, el AUC sigue en 0,97 y 0,98, pero las 300 rampas ya cayeron por ruido, en la mediana hacia r igual a menos 0,30, lejos del pliegue en menos 0,385. El indicador sube, pero lo que se mide es una caída por ruido, no la bifurcación. El AUC no dice si el aviso llega a tiempo.

Y una sorpresa: la varianza iguala o supera al AR(1) en 24 de las 25 celdas, y en 22 gana en las tres semillas. La ventaja del AR(1), la robustez al ruido, este barrido no la prueba. [Opcional, si vas sobrado de tiempo, unos 10 s: "Eso sí lo probé aparte, subiendo solo el ruido: la varianza da falsa alarma y el AR(1) no. Está en el respaldo B6."]

**Transición:** Cierro con lo que me llevo de todo esto.

**Si te quedas sin tiempo:** corta "Una" a su primera frase y deja de "Tres" solo "las 300 rampas ya cayeron por ruido, lejos del pliegue". No cortes la sorpresa de la varianza, el control que cae solo ni la caída por ruido del σ = 0,15; son las cosas honestas del slide.

---

## Slide 15 — Qué nos dice y por qué importa

**Tiempo:** 1:30 (acumulado 17:45)

**En pantalla:** tres conclusiones, una frase sobre por qué importa, el enlace al repositorio y "Preguntas". El deck trae un marcador en lugar del enlace: escribe tú el enlace real antes de presentar (ver el checklist).

**Decir:**

¿Qué nos dice todo esto? Tres cosas. Primero: en un modelo donde conozco la verdad, la varianza y el AR(1) suben antes del salto, y con un grupo de control las separo del azar: AUC cercano a 1 cuando miro hasta 83,5 unidades antes del pliegue. Si solo miro hasta el 40 % de la rampa, el AUC baja a 0,95 con varianza y 0,87 con AR(1), y detecto el 78 % y el 46 %. Segundo: eso tiene condiciones; si la rampa es corta, o si el ruido es tan grande que el sistema cae solo, la señal se pierde. Tercero: estas señales dicen que nos acercamos a un pliegue, no cuándo vamos a caer. Y todo esto es un modelo de juguete con datos simulados: no demuestra que funcione en el clima o en un ecosistema real.

¿Por qué importa igual? Porque muestra qué hay que revisar antes de creer una alarma: un control, el nivel de ruido, la ventana y hasta dónde se mira.

Todo el código está en un repositorio, con semillas fijas, pruebas y un comando que reproduce todas las figuras; el enlace está en pantalla. En mi trabajo diario construyo sistemas de datos, y quise tratar este proyecto con el mismo rigor. Gracias. Quedo atento a sus preguntas.

**Transición:** [fin; deja el slide con el enlace y las preguntas visible durante el espacio de preguntas]

**Si te quedas sin tiempo:** corta el párrafo de "por qué importa" y la frase de tu trabajo; no cortes las tres conclusiones, los números del 40 % ni la limitación del modelo de juguete.

---

## Respaldo B1 — Linealización y proceso de Ornstein–Uhlenbeck

**En pantalla:** diapositiva oculta con la derivación: expansión de f cerca del equilibrio, solución por factor integrante, varianza por la isometría de Itô.

**Decir:**

Parto de dx igual a f dt más σ dW y escribo x como x asterisco más y. Expando f en y: queda λ y más un término cuadrático y más términos mayores, con λ igual a uno menos tres x asterisco al cuadrado. Si tiro el término cuadrático y los siguientes, tengo dy igual a λ y dt más σ dW.

Se resuelve multiplicando por e a la menos λ t: y de t es e a la λ t por y cero, más σ por la integral de e a la λ por t menos s, dW de s. Es una gaussiana de media cero. Su varianza sale de la isometría de Itô: σ cuadrado por la integral de e a la dos λ por t menos s, que da σ cuadrado sobre dos valor absoluto de λ por uno menos e a la menos dos valor absoluto de λ t. En tiempo largo queda σ cuadrado sobre dos valor absoluto de λ.

Un chequeo rápido por balance: la derivada de la varianza es dos λ por la varianza más σ cuadrado. La fuerza restauradora quita varianza y el ruido la pone; el balance da el mismo resultado. La autocorrelación es e a la λ τ, y muestreada cada Δt es un AR(1) con coeficiente e a la λ Δt.

¿Cuándo vale la aproximación? Es el límite de σ pequeño. A r igual a cero y σ igual a 0,05, la simulación da varianza 0,00063 contra 0,00062 de la teoría, y AR(1) 0,365 contra 0,368. Cerca del pliegue se degrada: a r igual a menos 0,33, la varianza simulada supera a la teórica en 9 % con σ igual a 0,05 (cociente 1,093), en 3 % con σ igual a 0,03 (1,027), y con σ igual a 0,015 ya es 1,006. A la vez, el AR(1) simulado es 0,733 contra 0,714 de la teoría: los puntos violetas del slide 10 quedan por encima de la curva por eso, y la distribución ya es algo asimétrica, porque el valle plano no es un resorte perfecto. Además, cerca del pliegue λ se va como la raíz de r más r crítico, y por eso la varianza crece como r más r crítico a la menos un medio.

---

## Respaldo B2 — Cardano y raíces complejas

**En pantalla:** diapositiva oculta con la cúbica x³ − x − r = 0, el discriminante, la fórmula de Cardano y la forma trigonométrica.

**Nota para ti (no se dice):** la fórmula de la foto de tus apuntes resuelve x³ + x + r = 0, que tiene el término lineal con signo contrario. Esa cúbica tiene siempre una sola raíz real (su discriminante es −(4 + 27 r²), negativo para todo r) y no tiene bifurcación. Nuestro modelo es x³ − x − r = 0.

**Decir:**

Ojo con el signo del término lineal: con x al cubo más x más r igual a cero habría una sola raíz real para todo r y ninguna bifurcación; nuestro modelo es x al cubo menos x menos r igual a cero, y ese signo menos es lo que crea los tres equilibrios.

Es una cúbica deprimida, x al cubo más p x más q, con p igual a menos 1 y q igual a menos r. El discriminante es 4 menos 27 r al cuadrado: hay tres raíces reales cuando el valor absoluto de r es menor que r crítico, y en el borde dos raíces coinciden. Con x igual a u más v y la condición u por v igual a un tercio, u al cubo y v al cubo son las raíces de z cuadrado menos r z más un veintisieteavo, es decir, r medios más o menos raíz de r cuadrado sobre cuatro menos un veintisieteavo.

Si el valor absoluto de r supera r crítico, el radicando es positivo, hay una raíz real y se calcula con raíces cúbicas reales. Si es menor, el radicando es negativo, u al cubo es complejo y aparece el casus irreducibilis: el resultado es real pero hay que pasar por números complejos. Ejemplo con r igual a cero: u al cubo es i sobre tres raíz de tres, u vale 0,5 más 0,2887 i, y u más su conjugado da la raíz 1; las otras dos son menos 1 y 0. Para no pasar por complejos, uso la forma trigonométrica: x sub k igual a dos sobre raíz de tres por coseno de un tercio de arcocoseno de tres raíz de tres sobre dos por r, menos dos pi k sobre tres, con k igual a 0, 1, 2. El argumento del arcocoseno llega a más o menos 1 exactamente en los dos pliegues: a más 1 en r igual a más r crítico y a menos 1 en r igual a menos r crítico.

---

## Respaldo B3 — Tau de Kendall y AUC

**En pantalla:** diapositiva oculta con la definición de tau, de AUC y de la tasa de detección con 5 % de falsas alarmas (TPR a 5 % de FPR).

**Decir:**

El tau de Kendall es una correlación de rangos: cuento los pares concordantes menos los discordantes, dividido por el número total de pares. Mide cuánto sube un indicador con el tiempo sin importar la escala; no cambia con transformaciones monótonas y aguanta valores atípicos. Submuestreo el indicador cada W sobre 40 muestras para reducir el traslape entre ventanas consecutivas.

El AUC es la probabilidad de que un tau de la rampa sea mayor que un tau del control, contando los empates como media probabilidad; es la probabilidad de Mann y Whitney. 0,5 es no discriminar y 1 es separar perfecto.

La tasa de detección con 5 % de falsas alarmas es más operativa: tomo el percentil 95 de los taus del control como umbral de alarma, así solo 5 % del control dispara una falsa alarma, y miro qué fracción de la rampa lo supera. Para el AR(1) ese umbral es 0,47. En la línea base el AR(1) detecta el 99 % de la rampa con ese umbral y la varianza, el 100 %.

---

## Respaldo B4 — Detalles del barrido y límites

**En pantalla:** diapositiva oculta con la grilla del barrido y los dos mapas de calor de "control que cae solo" y "rampa que cae antes del 60 % del recorrido". Raya = más del 20 % de los controles caen; con σ = 0,30 y duraciones 100 y 200 ya caen 10 % y 20 %, sin raya.

**Decir:**

El barrido cruza cinco niveles de ruido, 0,03; 0,05; 0,10; 0,15 y 0,30, con cinco duraciones de rampa, 100, 200, 400, 1000 y 2000, y tres semillas, con 300 corridas por grupo. La ventana es siempre el 10 % de la rampa, de 20 muestras en duración 100 a 400 muestras en duración 2000, y el detrending usa un cuarto de la ventana. Los rangos de las tablas salen de solo tres semillas: son un rango indicativo, no un intervalo de confianza. Semilla por semilla, la varianza supera al AR(1) en las tres semillas en 22 de las 25 celdas; las excepciones son σ igual a 0,10 con duración 100, y σ igual a 0,30 con duraciones 100 y 1000.

Ventana contra duración, con σ igual a 0,05, 300 corridas y una semilla. Con la misma ventana de 10 unidades, la rampa de 2000 da un AUC de 0,97 con varianza y 0,94 con AR(1), y la de 100 da 0,63 y 0,61. Con una ventana de 30 unidades, la rampa de 100 solo sube a 0,74 y 0,68. Con la ventana de 200 unidades y un detrending de 12,5 en lugar de 50, la rampa de 2000 da 0,999 y 0,991: el detrending importa poco ahí. Y la rampa corta no es adiabática: con duración 100, al final del análisis el tiempo de relajación es 2,3 contra 4,15 unidades que faltan al pliegue; con duración 2000, 2,3 contra 83.

Cada corrida se analiza hasta que cae, menos un margen de 50 unidades, o hasta el 60 % del recorrido, lo que ocurra primero. Una caída es la primera muestra con x menor que cero. Las corridas con menos de 15 puntos utilizables se descartan.

Los mapas de calor: a la izquierda, el control que cae solo: 0 % hasta σ igual a 0,15 y, con σ igual a 0,30, 10 %, 20 %, 35 %, 70 % y 89 % según la duración. A la derecha, la rampa que cae antes del 60 % del recorrido: con σ igual a 0,15 va de 21 % a 100 %, y con σ igual a 0,30 está entre 88 % y 100 %. Hay que distinguir dos cosas. Con σ igual a 0,15 todas las corridas son válidas, 300 de 300, y caen por ruido antes del pliegue: el AUC se calcula sobre el tramo previo a la caída. El sesgo de supervivencia propiamente dicho aparece con σ igual a 0,30: con duración 2000 quedan 112 de 300 rampas y 214 de 300 controles. Truncar cada control en los mismos tiempos que las rampas cambia el AUC en menos de 0,01 con σ hasta 0,15, así que el AUC en sí no está sesgado; lo que pasa es que ya no habla del pliegue.

Límites: modelo de juguete con verdad conocida, sin datos reales; el AUC no mide si el aviso llega a tiempo; la teoría lineal se degrada cerca del pliegue y con σ grande; las señales no dicen cuándo; y el resultado depende de decisiones del analista, como la ventana, el detrending y hasta dónde se mira.

---

## Respaldo B5 — Resultados estáticos (plan B de A3)

**En pantalla:** dos paneles con la varianza móvil (izquierda) y el AR(1) móvil (derecha) de rampa y control, con la mediana y la banda de percentiles 10 a 90 %, hasta t = 1200. Si hace falta, el histograma del slide 13.

**Decir:**

Si el video no corre, esta es la misma historia en estático. Mediana de las 300 corridas con banda entre los percentiles 10 y 90. En verde, el control: la varianza y el AR(1) se quedan planos. En violeta, la rampa: la varianza móvil sube y casi se triplica, y el AR(1) pasa de alrededor de 0,37 a alrededor de 0,72 hacia t igual a 1200. Las bandas de rampa y control se separan; en el AR(1) tardan más en separarse y se superponen hasta cerca de la mitad del recorrido. Los números de resumen son los mismos del slide 12: AUC de 0,9998 con varianza y 0,995 con AR(1), y detección de 100 % y 99 % con 5 % de falsas alarmas.

---

## Respaldo B6 — El AR(1) no se deja engañar por ruido creciente (en este modelo)

**En pantalla:** a la izquierda, dos filas de AUC contra el control (A: el ruido sube de 0,05 a 0,15 con r = 0; B: el sistema se acerca a la bifurcación), con la varianza como círculo lleno y el AR(1) como círculo vacío, y la línea del azar en 0,5. A la derecha, varianza móvil y AR(1) móvil del caso "el ruido sube" frente al control. Los números salen de `results/confound.json` (tres semillas juntas, 900 corridas por grupo; los intervalos son bootstrap sobre las corridas).

**Decir:**

Esta es la prueba que le faltaba al barrido, y que sí mueve el ruido. Dejo r quieto en cero, o sea, sin bifurcación, y hago subir el ruido linealmente de 0,05 hasta 0,15 durante la rampa; lo comparo con el control, que mantiene el ruido en 0,05. Si un indicador sube aquí, es una falsa alarma, porque no hay ningún punto de quiebre cerca.

El resultado es claro. La varianza sube, y tiene un AUC de 1,000. El AR(1) tiene un AUC de 0,517, con intervalo de 0,490 a 0,545: no se distingue del azar. Con un ruido final de 0,10 pasa lo mismo: la varianza da 0,9999 y el AR(1), 0,489. Y si miro la tasa de falsas alarmas fijando 5 % en el control, la varianza dispara en el 100 % de las corridas y el AR(1) en 5,6 %, que es lo nominal. Eso es lo que predice la teoría lineal, porque la autocorrelación e a la λΔt no depende de σ.

Cuando el sistema sí se acerca al pliegue y además el ruido sube hasta 0,15, comparado contra el caso de solo ruido, que es la pregunta correcta, el AR(1) mantiene un AUC de 0,993 y la varianza cae a 0,904.

Cuatro cautelas. Probé solo ruido blanco, con subida lineal y dos niveles finales, 0,10 y 0,15. Solo con r constante en cero o con el pliegue a la vez; ruido multiplicativo o con memoria no se probó. En los casos mezclados, el 46 % de las rampas con ruido hasta 0,10 y el 89 % con ruido hasta 0,15 caen antes del punto de análisis, así que valen las mismas cautelas sobre la caída por ruido. Y el barrido principal no cambia: con ruido constante, la varianza iguala o supera al AR(1).

---

## Extras

### (a) Glosario

1. **Bifurcación silla-nodo (pliegue, tangente):** el evento en que un equilibrio estable y uno inestable chocan y desaparecen al variar el parámetro. En una dimensión, en el instante del choque queda un solo equilibrio semiestable (atrae por un lado y repele por el otro). Se llama "silla-nodo" por la versión en dos dimensiones, ẋ = r + x², ẏ = −y, donde chocan un nodo estable y un punto silla.
2. **Punto silla (y nodo):** el punto silla es un tipo de equilibrio en dos o más dimensiones con valores propios de signos opuestos; atrae a lo largo de una dirección y repele a lo largo de otra. El nodo estable atrae en todas las direcciones. No existe en una dimensión; ahí el equilibrio inestable es un simple repulsor. Se reserva el término para el equilibrio, no para el evento.
3. **Equilibrio estable / inestable / semiestable:** estable si una perturbación pequeña decae, inestable si crece, semiestable si decae por un lado y crece por el otro (el caso del pliegue).
4. **λ (tasa de crecimiento):** derivada de la fuerza en el equilibrio, λ = f′(x*) = 1 − 3x*². Negativa significa estable, y |λ| es la tasa de recuperación.
5. **Matriz jacobiana:** matriz de derivadas parciales de la dinámica en el equilibrio; en una dimensión es el número λ. Sus valores propios dicen la estabilidad.
6. **Desaceleración crítica:** cerca del pliegue λ → 0, el tiempo de recuperación 1/|λ| diverge y el sistema se vuelve lento y con fluctuaciones más grandes y más largas. En rigor, "crítico" se dice de transiciones continuas; aquí el pliegue es un punto espinodal de una transición de primer orden (ver la pregunta 22).
7. **Sobreamortiguado / flujo gradiente:** dinámica donde la velocidad es proporcional a la fuerza (sin inercia) y la fuerza es menos la derivada de un potencial; la bola solo baja por el paisaje.
8. **Ruido blanco:** perturbación sin memoria, con el mismo contenido en todas las frecuencias; es la derivada formal del proceso de Wiener y no existe como función ordinaria.
9. **Proceso de Wiener:** movimiento browniano matemático: empieza en cero, trayectorias continuas, incrementos independientes y gaussianos con varianza igual al tiempo transcurrido.
10. **Euler–Maruyama:** esquema numérico para ecuaciones diferenciales estocásticas: x_{n+1} = x_n + f Δt + σ √Δt η, con η normal estándar. La raíz de Δt viene de que la varianza del ruido debe crecer linealmente con el tiempo. (Itô y Stratonovich, dos formas de interpretar la integral estocástica, coinciden cuando el ruido es aditivo, como aquí.)
11. **Proceso de Ornstein–Uhlenbeck (OU):** partícula en un pozo armónico con fricción grande y ruido blanco, dy = λ y dt + σ dW con λ < 0; es gaussiano, con varianza σ²/(2|λ|) y autocorrelación e^{λτ}. (El artículo de 1930 trata sobre todo de la velocidad de una partícula browniana libre con fricción, que es el mismo proceso.)
12. **AR(1):** modelo autorregresivo de orden uno, y_{n+1} = φ y_n + ruido; aquí φ = e^{λΔt} es la autocorrelación a un paso.
13. **Autocorrelación:** correlación de una serie consigo misma con un retardo; mide la memoria.
14. **Detrending:** quitar la tendencia lenta restando una media móvil; actúa como filtro de altas frecuencias. Si la ventana es muy corta borra la señal; si es muy larga deja pasar la tendencia.
15. **Tau de Kendall:** correlación de rangos, (concordantes − discordantes) dividido por el número de pares; aquí mide cuánto sube un indicador con el tiempo.
16. **AUC:** área bajo la curva ROC, igual a la probabilidad de que una corrida de rampa elegida al azar tenga tau mayor que una de control; 0,5 es azar y 1 es separación perfecta.
17. **Tasa de detección y de falsas alarmas (TPR / FPR):** fracción de rampas detectadas y fracción de controles que disparan la alarma. Se fija un 5 % de falsas alarmas y se reporta la tasa de detección.
18. **Histéresis y biestabilidad:** el estado depende de la historia; subir y bajar el parámetro da saltos en valores distintos, porque entre los dos pliegues coexisten dos estados estables.
19. **Escape de Kramers:** salida por ruido de un valle de potencial; su tasa crece con σ y cae exponencialmente con la barrera, que se anula en el pliegue.
20. **Sesgo de supervivencia:** analizar solo las corridas que llegan hasta cierto punto, cuando las que caen antes se truncan o quedan fuera.

### (b) Qué NO afirmar

- **No presentes A2 como el experimento.** La animación usa σ = 0,16 (3,2 veces el ruido del experimento), una rampa unas 15 veces más rápida y una corrida elegida para que no caiga; con ese ruido y esa rampa cae el 21 % de las corridas y el 25 % baja de 0,2. Con σ = 0,05 y la misma rampa, ninguna.
- **No afirmes que el sistema cae exactamente en el pliegue.** En la línea base, el pliegue se cruza en t = 1283,5 y la mediana de caída es t = 1263,25: caen unas 20 unidades antes, y el 76 % de las corridas cae antes del pliegue. Sin ruido caería 28,5 unidades después; el ruido la adelanta unas 49. Con σ = 0,10 y σ = 0,15, todas caen antes del pliegue (mediana de r en la caída: −0,34 y −0,30).
- **No afirmes que "AUC cercano a 1" vale para cualquier horizonte.** El análisis termina al 60 % de la rampa, 83,5 unidades antes del pliegue, y lo fijé sabiendo dónde está el pliegue; un observador real no lo sabe. Si se mira solo hasta el 30 % de la rampa, el AUC es 0,82 con varianza y 0,70 con AR(1); hasta el 40 %, 0,95 y 0,87.
- **No afirmes que todo salto avisa.** Solo las bifurcaciones con λ → 0 y un parámetro que se acerca despacio; el ruido y la tasa no dan esa señal, y una rampa corta tampoco (AUC cerca de 0,6).
- **No afirmes que esto es un modelo del clima ni de un ecosistema.** Es un modelo de juguete unidimensional con verdad conocida.
- **No afirmes que los datos son reales.** Son simulados. Con una serie real no hay un control natural, y una sola serie no permite estimar falsas alarmas.
- **No afirmes que el resultado vale en general.** Es el mejor caso: señal con verdad conocida, ruido blanco aditivo y parámetro que cambia linealmente.
- **No afirmes que el control está libre de caídas.** Con σ = 0,30 el control también cae solo: 10 %, 20 %, 35 %, 70 % y 89 % según la duración (de 100 a 2000).
- **No llames "sesgo de supervivencia" a lo que pasa con σ = 0,15.** Ahí las 300 rampas son válidas, pero cayeron por ruido mucho antes del pliegue (mediana de r en la caída: −0,30 contra −0,385): lo que se mide es una caída por ruido, no la bifurcación. El sesgo de supervivencia propiamente dicho aparece con σ = 0,30: con duración 2000 solo quedan 112 de 300 rampas y 214 de 300 controles válidos, y ese AUC (0,63) no se puede interpretar.
- **No afirmes que la ventana y la duración están confundidas sin matices.** Se comprobó aparte (σ = 0,05, una semilla): con la misma ventana de 10 unidades, la rampa de 2000 da AUC 0,94 con AR(1) y la de 100 da 0,61; con una ventana de 30 unidades, la de 100 sube a 0,68. Manda la duración, y la rampa corta no es adiabática.
- **No afirmes que la linealización es exacta.** Es una aproximación: a r = −0,33 y σ = 0,05 la varianza simulada está 9 % por encima de la teoría de OU (cociente 1,093), y los puntos de autocorrelación del slide 10 quedan por encima de la curva.
- **No afirmes que "el AR(1) es mejor que la varianza".** En este barrido la varianza iguala o supera al AR(1) en 24 de las 25 celdas, y en 22 gana en las tres semillas (las excepciones son σ = 0,10 con duración 100, y σ = 0,30 con duraciones 100 y 1000). La ventaja que se le atribuye al AR(1) es la robustez a cambios en la amplitud del ruido, y este barrido no la prueba porque no mueve el ruido durante la rampa. Esa ventaja sí aparece en el experimento aparte de ruido creciente (B6): con r constante y el ruido subiendo, la varianza da falsa alarma y el AR(1) no. Pero eso se probó solo con ruido blanco, subida lineal y dos niveles finales de ruido.
- **No afirmes que la señal dice cuándo.** Dice que el sistema se acerca a un pliegue; no da una fecha.
- **No afirmes que el AUC alto implica un aviso útil.** El AUC no mide si el aviso llega antes de la caída.
- **No presentes los rangos del barrido como intervalos de confianza.** Salen de tres semillas: son un rango, indicativo.
- **No afirmes nada sobre el curso ni sobre el profesor** que no sepas con certeza.

### (c) Plan B

**Si un video (A1, A2, A3) no corre.** PowerPoint reproduce los videos incrustados con un clic; si no arranca, haz clic en el video y mira que el botón de reproducción esté visible, o usa Reproducir en la pestaña Reproducción. Si sigue sin funcionar, no pierdas tiempo: deja el poster en pantalla y di la frase de rescate.
- A1, con el poster (r = −0,37): "Esto es un cuadro de la animación. El valle derecho se va aplanando y, al llegar a menos 0,385, desaparece y la bola cae al valle de la izquierda."
- A2, con el poster (r = −0,28): "Esto es una ilustración con más ruido que el experimento; aquí la bola fluctúa más y más lento a medida que baja r, y esta corrida no cae."
- A3: abre el respaldo B5 (resultados estáticos) y cuenta lo mismo con la figura: varianza y AR(1) suben en la rampa y se quedan planos en el control.

**Si el proyector no tiene video** (o el computador del salón no lo reproduce), usa los posters igual que arriba. Los posters son imágenes fijas que siempre se ven.

**Si falla el computador:** ten el PDF en USB, en la nube y en el celular; presenta desde el PDF, sin animaciones, con las frases de rescate. Si ni el PDF abre, cuéntalo sin diapositivas: es una idea de tres frases (hay un aviso físico, se mide con varianza y autocorrelación, y falla en situaciones concretas).

**Si vas corto de tiempo, corta en este orden:**
1. La mención del caos y los ejemplos del slide 2.
2. La lista de tres tipos de punto de quiebre del slide 3.
3. La analogía del ferromagneto del slide 7.
4. La raíz de dt del slide 8.
5. La explicación de AR(1) y la imagen de inyectar y sacar varianza del slide 10.
6. El slide 13 acortado a su primera mitad.
7. Cortar "Una" del slide 14 a su primera frase.

Nunca cortes: la definición de λ (slide 5), la advertencia de que A2 es una ilustración, las fórmulas del slide 10, que la rampa cae antes del pliegue (slide 11), los números del slide 12 y que miras solo hasta el 60 %, el control que cae solo, la caída por ruido con σ = 0,15 y la frase "no dice cuándo" del slide 15.

**Si vas largo de tiempo** (te sobran más de 2 minutos): amplía el slide 14 con el segundo mapa (B4), o muestra B6; no añadas contenido nuevo.

### (d) Preguntas difíciles

**1. ¿Por qué no usaste datos reales?**
Porque con una serie real no conozco la verdad: no sé si el sistema iba a caer ni cuándo, y no tengo un grupo de control para estimar falsas alarmas. En el modelo sé que el pliegue está en 0,385 y puedo repetir el experimento 300 veces. Es el paso previo: calibrar el método donde puedo comprobarlo. Los datos reales son el siguiente paso, con sus propios problemas: ruido de medición, pocos datos y series no estacionarias.

**2. ¿Por qué un modelo 1D?**
Es la forma normal del pliegue: cerca de una bifurcación silla-nodo, un sistema de más dimensiones se reduce a una ecuación en la dirección donde λ tiende a cero (reducción a la variedad central). El resto de direcciones decae rápido y no importa. La limitación es que los sistemas reales tienen más dimensiones, ruido que no siempre es aditivo ni blanco, y mi modelo no prueba eso.

**3. ¿Por qué el tau de Kendall y no el valor del indicador?**
El valor absoluto de la varianza depende de σ, de las unidades y del detrending, así que no es comparable entre series. El tau mide solo si el indicador sube con el tiempo, no cambia con transformaciones monótonas y aguanta valores atípicos. El costo es que pierde la magnitud, y su p-valor usual no sirve porque las ventanas se traslapan; por eso uso el control para calibrar el umbral.

**4. ¿Por qué AR(1) y no solo varianza?**
Honestamente, en mi barrido la varianza iguala o supera al AR(1) en 24 de las 25 celdas, así que mis datos no apoyan que el AR(1) sea mejor. La ventaja que se le atribuye es la robustez: la varianza también sube si aumenta la amplitud del ruido σ sin que haya bifurcación, mientras que el AR(1) depende de λ y no de σ en el modelo lineal. Mi barrido mantiene σ constante, así que no pone a prueba esa ventaja; la probé aparte (B6): con r constante y el ruido subiendo de 0,05 a 0,15, la varianza da AUC 1,000 y el AR(1), 0,517, es decir, solo la varianza da falsa alarma. Ver también la pregunta 20.

**5. ¿Qué pasa si el ruido es coloreado?**
No lo probé; mi ruido es blanco. Si el ruido tiene memoria constante, el AR(1) sube de nivel, pero el control, con el mismo ruido, lo absorbe. El problema es si esa memoria cambia durante la rampa: ahí el AR(1) sube sin que λ cambie y da falsa alarma. Es una de las cosas que haría con más tiempo.

**6. ¿Cómo se elige la ventana?**
Es un compromiso: una ventana corta da estimaciones muy ruidosas, y una larga mezcla estados con valores distintos de r y reduce cuántos puntos quedan antes de la caída. En el barrido usé el 10 % de la rampa y un cuarto de eso para el detrending. Lo comprobé aparte (σ = 0,05, una semilla): con la misma ventana de 10 unidades, la rampa de 2000 da AUC 0,97 con varianza y 0,94 con AR(1), y la de 100 da 0,63 y 0,61; con una ventana de 30 unidades, la de 100 solo sube a 0,74 y 0,68. O sea que manda la duración, y el resultado depende de decisiones del analista.

**7. ¿Qué es la desaceleración crítica y por qué ocurre?**
Cerca del pliegue, f y su derivada se anulan a la vez, así que λ tiende a cero. Al linealizar, una perturbación decae como e^{λt}, de modo que el tiempo de recuperación 1/|λ| diverge y el sistema se vuelve lento. Cerca del pliegue, |λ| crece como la raíz de r más r crítico, por eso la varianza σ²/(2|λ|) y la autocorrelación e^{λΔt} suben.

**8. ¿Esto sirve para el clima o para la AMOC?**
Mi trabajo no lo demuestra: es un modelo de juguete con datos simulados. Hay investigadores que buscan estas señales en datos climáticos, y las conclusiones son debatidas; no me corresponde decir si algún componente del clima va a cruzar un punto de quiebre. Lo que sí aporta mi proyecto es una lista de cosas por revisar antes de creer una alarma: un control, el nivel de ruido, la ventana, hasta dónde se mira y si el sistema cae por ruido antes del pliegue.

**9. ¿Se puede predecir el punto de quiebre con fecha?**
No. La señal dice que el sistema se acerca a un pliegue, no cuándo cae. Además, con ruido la caída ocurre antes: en mi línea base la mediana de caída es t = 1263,25 contra un pliegue en t = 1283,5, y el 76 % cae antes del pliegue; con σ = 0,15, la mediana de r en la caída es −0,30, lejos de −0,385.

**10. ¿Cuál es la diferencia entre bifurcación, ruido y tasa (tipos de punto de quiebre)?**
En el punto de quiebre por bifurcación el parámetro cruza un valor crítico y el estado estable desaparece. En el de ruido, las fluctuaciones sacan al sistema de su valle aunque el parámetro siga en la zona biestable. En el de tasa, el parámetro cambia tan rápido que el sistema no alcanza a seguir el equilibrio. La señal de desaceleración crítica solo está justificada para el primero.

**11. ¿Qué es el ruido de Wiener y por qué raíz de dt?**
Es un proceso con incrementos independientes y gaussianos, de varianza igual al tiempo transcurrido. Por eso, en un paso Δt, el incremento tiene desviación √Δt. Si usara Δt, el ruido se desvanecería al afinar la malla; con √Δt, n pasos acumulan varianza σ²T sin importar n.

**12. ¿Por qué el control no basta si el ruido es grande?**
Porque el control también cae. Con σ = 0,30, el 89 % de los controles de duración 2000 cae solo, así que ya no es un grupo "sin quiebre" y el AUC no se puede interpretar. Habría que definir otra referencia, por ejemplo truncar cada control en los mismos tiempos que las rampas; lo probé con σ hasta 0,15 y el AUC cambia en menos de 0,01.

**13. ¿Qué harías con más tiempo?**
Cuatro cosas: probar ruido coloreado, separar la ventana de la duración en todo el barrido, ampliar el experimento de ruido creciente (B6), que hice solo con subida lineal y dos niveles finales, y combinarlo con el barrido completo. Después, pasar a un sistema de dos dimensiones y, por último, a datos reales con un control construido (series sustitutas).

**14. ¿Cómo se conecta esto con ingeniería de datos y ML?**
Todo está construido como un pipeline reproducible: semillas fijas, un comando que regenera figuras y animaciones, resultados en Parquet que se consultan con DuckDB, pruebas con oráculos físicos y verificación automática en integración continua. La evaluación (AUC, tasa de detección a falsas alarmas fijas, intervalos bootstrap) es la de un clasificador, y la pregunta de si el aviso llega a tiempo es la de cualquier sistema de detección en producción.

**15. ¿Qué es λ y por qué la jacobiana?**
λ es la derivada de la fuerza en el equilibrio: dice con qué tasa crece o decae una perturbación pequeña. En una dimensión es un número; en dimensión mayor es la matriz jacobiana, con un valor propio por dirección. Lo que importa para el pliegue es el valor propio que cruza cero.

**16. ¿Qué es la histéresis y por qué importa?**
El estado depende de la historia: al bajar r el sistema salta en menos 0,385, y al subir salta en más 0,385, así que hay un lazo de ancho 0,77 con dos estados posibles. Importa porque después de un quiebre no basta devolver el parámetro al valor anterior; hay que pasarlo hasta el otro lado.

**17. ¿Por qué en la animación A1 la bola cae después de pasar el pliegue, y en el experimento con ruido, antes?**
Sin ruido, cerca del pliegue la bola reacciona cada vez más lento, así que cae un poco después de que el equilibrio desaparece: en la rampa del experimento, 28,5 unidades después. Con ruido, una fluctuación grande la saca del valle antes de que desaparezca: mediana de caída en t = 1263,25 contra el pliegue en t = 1283,5. Con σ = 0,05, 20 unidades antes del pliegue la barrera de potencial vale 4,7·10⁻⁴ y a 30 unidades, 8,7·10⁻⁴, menos que σ²/2 = 1,25·10⁻³; por eso el escape por ruido le gana al retardo.

**18. ¿Qué diferencia hay entre bifurcación silla-nodo y punto silla?**
La bifurcación silla-nodo es un evento: dos equilibrios chocan y desaparecen. El punto silla es un tipo de equilibrio en dos dimensiones o más, con valores propios de signos opuestos. En 1D, en el instante del choque solo queda un equilibrio semiestable. Se llama silla-nodo porque en la versión de dos dimensiones chocan un nodo estable y un punto silla.

**19. ¿Y los falsos positivos en un caso real?**
No se pueden estimar con una sola serie real, porque no hay un control natural. En la simulación sí, y por eso el 5 % de falsos positivos del slide 13 está calibrado contra el control; en la realidad habría que construir ese control con series sustitutas o con datos de un periodo sin cambio.

**20. Entonces, ¿el AR(1) es mejor que la varianza?**
Depende de qué ruido haya. Con ruido constante, mi barrido da a la varianza igual o mejor resultado en 24 de las 25 celdas. Pero en el experimento aparte con r constante y el ruido subiendo de 0,05 a 0,15, la varianza da falsa alarma (AUC 1,000) y el AR(1) no (AUC 0,517, con 5,6 % de alarmas, lo nominal). Y cuando el pliegue y el ruido creciente ocurren a la vez, el AR(1) mantiene AUC 0,993 frente a 0,904 de la varianza. Así que ninguno domina: la varianza tiene más potencia si σ es constante y el AR(1) es más robusto si σ cambia; eso sí, solo probé ruido blanco con subida lineal.

**21. ¿Cómo se pasa de la ecuación de Langevin a la tuya?**
La de Langevin tiene inercia, m·ẍ = −γẋ − V′(x) + ruido. Con fricción grande se desprecia la inercia y queda γẋ = −V′(x) + ruido, o sea dx = f dt + σ dW (límite sobreamortiguado, de Smoluchowski). La relación de fluctuación–disipación fija σ² = 2kT/γ, y la barrera de Kramers es ΔV dividida por σ²/2.

**22. ¿Es "desaceleración crítica" o es otra cosa?**
En sentido estricto "crítico" se usa para transiciones continuas. Aquí hay un pliegue, que es el punto espinodal de una transición de primer orden: el modelo es un campo medio tipo Landau, con r como campo magnético y r crítico como campo coercitivo. El λ → 0 es el mismo fenómeno, pero λ crece como la raíz de r más r crítico y no como r menos r crítico, y por eso la varianza diverge como r más r crítico a la menos un medio.

**23. ¿La rampa es adiabática?**
En la línea base sí: la rampa va a 3·10⁻⁴ por unidad de tiempo, el tiempo de relajación pasa de 0,5 en r = 0 a 2,3 al final del análisis, cuando faltan 83 unidades para el pliegue, y el sistema deja de seguir al equilibrio solo unas 7,7 unidades antes del pliegue. Con duración 100 no: la rampa va a 6·10⁻³ y al final del análisis la relajación es 2,3 contra 4,15 unidades al pliegue. Es parte de por qué fallan las rampas cortas.

**24. ¿Por qué defines la caída como x < 0, y por qué analizas hasta el 60 %?**
x < 0 está a medio camino entre las dos ramas y es una elección arbitraria; el pliegue está en x = 0,577. El 60 % lo fijé sabiendo que el pliegue está al 64 % de la rampa: en datos reales no se conoce, y con menos datos el aviso es más débil (con el 40 % de la rampa, AUC 0,95 con varianza y 0,87 con AR(1)).

**25. ¿El detrending usa datos del futuro?**
Sí: la media móvil es centrada, y por eso corto el análisis 50 unidades antes de la caída. Para vigilancia en tiempo real habría que usar un filtro causal; no lo probé.

**26. ¿Cómo sabes que la subida no viene de quitar la tendencia?**
Lo comprobé aparte: un proceso con λ = −2 constante, cuya media sigue la misma rama que la rampa (de 1 a 0,69 en el tramo analizado), da un AUC de 0,47 con varianza y con AR(1) contra el mismo proceso con la media fija. O sea que el detrending no fabrica la señal.

**27. ¿Cuánto antes avisa?**
Depende de hasta dónde se mire. Mirando hasta el 30 % de la rampa, el AUC es 0,82 con varianza y 0,70 con AR(1), y la detección con 5 % de falsas alarmas es 35 % y 20 %. Hasta el 40 %: 0,95 y 0,87, y 78 % y 46 %. Hasta el 50 %: 0,996 y 0,967, y 99 % y 85 %. Hasta el 60 %, que son 83,5 unidades antes del pliegue: 0,9998 y 0,995, y 100 % y 99 %. Ese 60 % lo elegí sabiendo dónde está el pliegue, así que es el mejor caso.

**28. ¿Por qué la animación A2 usa más ruido que el experimento?**
Para que se vea a simple vista. Con σ = 0,05 las fluctuaciones son demasiado pequeñas para proyectarlas; con σ = 0,16 se ven, pero la rampa es unas 15 veces más rápida y cae el 21 % de las corridas, así que elegí una que no cae. Es una ilustración de la idea, no una medición; las mediciones están en los slides 12 a 14.

### (e) Números para memorizar

Todos salen de `results/key_numbers.json` (producido por `src/tipping/key_numbers.py`), salvo los de B6, que salen de `results/confound.json` (tres semillas juntas, 900 corridas por grupo).

| Concepto | Valor |
| --- | --- |
| Punto de quiebre (pliegue) r_c = 2/(3√3) | 0,385 |
| Tamaño del salto | √3 ≈ 1,73 |
| Ancho del lazo de histéresis, 2 r_c | 0,77 |
| Posición del pliegue en x | 0,577 |
| Tiempo en que la rampa cruza el pliegue | t = 1283,5 (el 64 % de la rampa) |
| Mediana de caída de las corridas con ruido | t = 1263,25 (unas 20 unidades antes) |
| Corridas de la rampa que caen antes del pliegue (σ = 0,05) | 76 % |
| Percentiles 5, 25, 75 y 95 del tiempo de caída | 1205, 1241, 1282 y 1313 |
| Caída sin ruido | t = 1312 (28,5 unidades después del pliegue) |
| Adelanto causado por el ruido | unas 49 unidades |
| Mediana de r en la caída, σ = 0,05; 0,10; 0,15 | −0,38; −0,34; −0,30 |
| Corridas que caen antes del pliegue, σ = 0,10 y 0,15 | 100 % |
| Barrera de potencial a 20 y 30 unidades del pliegue | 4,7·10⁻⁴ y 8,7·10⁻⁴ (σ²/2 = 1,25·10⁻³) |
| Corridas por grupo (rampa y control), línea base | 300 y 300 |
| Ruido de la línea base, σ | 0,05 |
| Duración de la rampa (línea base) | 2000 unidades de tiempo (r de 0 a −0,6) |
| Ventana y detrending (línea base) | 200 y 50 unidades de tiempo |
| Corridas de rampa que caen antes del 60 % del recorrido (línea base) | 3,3 % |
| Corridas del control que caen (línea base) | 0 % |
| AUC con varianza | 0,9998 |
| AUC con AR(1) | 0,995 (intervalo bootstrap 95 %: 0,991 a 0,998) |
| Tasa de detección con 5 % de falsas alarmas, varianza | 1,00 |
| Tasa de detección con 5 % de falsas alarmas, AR(1) | 0,99 (intervalo bootstrap 95 %: 0,97 a 1,00) |
| Tau mediano, rampa con varianza | 0,84 |
| Tau mediano, rampa con AR(1) | 0,76 |
| Tau mediano, control | 0,008 (varianza) y −0,002 (AR(1)) |
| Umbral de 5 % de falsas alarmas, AR(1) | 0,47 |
| Horizonte 30 %: AUC varianza y AR(1); detección | 0,82 y 0,70; 35 % y 20 % |
| Horizonte 40 %: AUC varianza y AR(1); detección | 0,95 y 0,87; 78 % y 46 % |
| Horizonte 50 %: AUC varianza y AR(1); detección | 0,996 y 0,967; 99 % y 85 % |
| Horizonte 60 %: AUC varianza y AR(1); detección | 0,9998 y 0,995; 100 % y 99 % |
| Unidades antes del pliegue al terminar el análisis (60 %) | 83,5 (r = −0,36) |
| Barrido: ruido σ | 0,03; 0,05; 0,10; 0,15; 0,30 |
| Barrido: duración de la rampa | 100, 200, 400, 1000, 2000 |
| Barrido: semillas | 3 (300 corridas por grupo) |
| Celdas donde la varianza iguala o supera al AR(1) (media) | 24 de 25 |
| Celdas donde la varianza gana en las tres semillas | 22 de 25 |
| AUC, σ = 0,05, duración 100: AR(1) y varianza | 0,60 y 0,62 |
| AUC, σ = 0,05, duración 2000: AR(1) y varianza (media de tres semillas) | 0,997 y 1,00 |
| AUC, σ = 0,15, duración 2000: AR(1) y varianza | 0,97 y 0,98 |
| Rampas que caen antes del 60 % del recorrido, σ = 0,15, duración 2000 | 100 % (300 de 300 válidas) |
| AUC, σ = 0,30, duración 2000: AR(1) y varianza | 0,63 y 0,68 |
| Rampas y controles válidos, σ = 0,30, duración 2000 | 112 de 300 y 214 de 300 |
| Control que cae solo, σ = 0,30, duraciones 100 a 2000 | 10 %, 20 %, 35 %, 70 %, 89 % |
| Ventana 10, duración 2000 y 100 (AUC varianza y AR(1)) | 0,97 y 0,94; 0,63 y 0,61 |
| Ventana 30, duración 100 (AUC varianza y AR(1)) | 0,74 y 0,68 |
| Tiempo de relajación frente a tiempo al pliegue, fin del análisis | duración 100: 2,3 y 4,15; duración 2000: 2,3 y 83 |
| Ritmo de la rampa, duración 100 y 2000 | 6·10⁻³ y 3·10⁻⁴ |
| A2: ruido, veces la rampa del experimento, y caídas | σ = 0,16 (3,2 veces), rampa 15 veces más rápida, cae el 21 % |
| A2: corridas que bajan de 0,2, σ = 0,16 y σ = 0,05 | 25 % y 0 % |
| Mínimo de x de la corrida elegida para A2 | 0,50 |
| Truncar el control como la rampa: cambio máximo del AUC (σ hasta 0,15) | menos de 0,01 |
| Control de detrending (media móvil, λ = −2): AUC varianza y AR(1) | 0,47 y 0,47 |
| Cociente varianza simulada / teórica a r = −0,33, σ = 0,05; 0,03; 0,015 | 1,093; 1,027; 1,006 |
| B6, ruido sube 0,05 → 0,15 con r = 0, AUC contra el control: varianza y AR(1) | 1,000 y 0,517 (intervalo 95 % del AR(1): 0,490 a 0,545) |
| B6, ruido sube 0,05 → 0,10 con r = 0, AUC contra el control: varianza y AR(1) | 0,9999 y 0,489 |
| B6, tasa de falsas alarmas con 5 % nominal (ruido hasta 0,15): varianza y AR(1) | 100 % y 5,6 % |
| B6, pliegue y ruido hasta 0,15, AUC contra solo ruido: AR(1) y varianza | 0,993 y 0,904 |
| B6, rampas que caen antes del 60 % del recorrido (ruido hasta 0,10 y 0,15) | 46 % y 89 % |

### (f) Referencias

- Scheffer, M. et al. (2009). Early-warning signals for critical transitions. *Nature* 461, 53–59.
- Ashwin, P., Wieczorek, S., Vitolo, R. y Cox, P. (2012). Tipping points in open systems: bifurcation, noise-induced and rate-dependent examples in the climate system. *Philosophical Transactions of the Royal Society A* 370, 1166–1184.
- Strogatz, S. H. *Nonlinear Dynamics and Chaos*, capítulo 3 (bifurcaciones en una dimensión, incluida la bifurcación silla-nodo). Westview Press.
- Einstein, A. (1905). Über die von der molekularkinetischen Theorie der Wärme geforderte Bewegung von in ruhenden Flüssigkeiten suspendierten Teilchen. *Annalen der Physik* 17, 549–560.
- Langevin, P. (1908). Sur la théorie du mouvement brownien. *Comptes Rendus de l'Académie des Sciences* 146, 530–533.
- Uhlenbeck, G. E. y Ornstein, L. S. (1930). On the theory of the Brownian motion. *Physical Review* 36, 823–841.
- Kramers, H. A. (1940). Brownian motion in a field of force and the diffusion model of chemical reactions. *Physica* 7, 284–304.
- Kendall, M. G. (1938). A new measure of rank correlation. *Biometrika* 30, 81–93.
- Dakos, V. et al. (2012). Methods for detecting early warnings of critical transitions in time series illustrated using simulated ecological data. *PLoS ONE* 7(7), e41010.

Verifica volúmenes y páginas antes de poner las referencias en un slide; el repositorio (`README.md`) lista las cuatro primeras y la de Uhlenbeck y Ornstein.

### (g) Checklist del día de la presentación

- [ ] Ensayar cronometrado tres veces, de pie y en voz alta; apunta el tiempo en cada punto de control (4:45, 11:00, 14:15).
- [ ] Ensayar al menos una vez sin leer el guion, solo con las notas del orador.
- [ ] Probar los tres videos (A1, A2, A3) en el computador del salón, con el proyector, antes de empezar.
- [ ] Tener el .pptx y el PDF en USB y en la nube, y el PDF también en el celular.
- [ ] Cargar el computador y llevar el cargador; desactivar notificaciones y el modo de ahorro de energía.
- [ ] Comprobar que las notas del orador NO se ven en el proyector (en PowerPoint: Presentación con diapositivas, Monitor, elegir el proyector como pantalla de la presentación); si hay duda, duplicar pantallas y tener el guion impreso o en el celular.
- [ ] Escribir en el slide 15 el enlace real del repositorio (el deck trae un marcador, no el enlace) y abrirlo para comprobar que carga. Si el repositorio no va a ser público el 3 de noviembre, cambia la frase del slide 15 por "Código disponible a pedido" con tu correo.
- [ ] Confirmar los números de los slides 12 y 14 contra la tabla de "Números para memorizar".
- [ ] Saber en qué número de diapositiva está cada respaldo (B1 a B6); en la presentación puedes escribir el número y pulsar Enter para saltar a una diapositiva oculta.
- [ ] Llevar agua y llegar 15 minutos antes.
- [ ] Releer "Qué NO afirmar" la noche anterior.
