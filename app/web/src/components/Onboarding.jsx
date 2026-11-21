import React, { useState } from "react";
import { Sparkles, Wand2, HardDrive, Shield, ArrowRight } from "lucide-react";
import { Modal } from "./ui";

const STEPS = [
  { icon: Sparkles, title: "Добро пожаловать в «Искру»", text: "Ваша локальная студия: фото, арт, видео со звуком и 3D-модели. Всё работает на этом компьютере — без подписок, без лимитов, без отправки картинок в интернет." },
  { icon: Wand2, title: "Как создать картинку", text: "Опишите идею своими словами по-русски, выберите пресет и нажмите «Создать» (или Ctrl+Enter). Кнопка «Улучшить» превратит короткую фразу в подробный промпт. «Черновик» — быстро, «Качество» — красиво." },
  { icon: HardDrive, title: "Модели и пресеты", text: "Раздел «Модели» — установленные модели и каталог Civitai / Hugging Face: установка в один клик. «Пресеты» — готовые настройки; любой можно изменить или создать свой." },
  { icon: Shield, title: "Безопасный режим", text: "По умолчанию 18+ контент скрыт. Переключайте щитом внизу слева или клавишей S. В «Настройках» можно поставить PIN-код. Все горячие клавиши — по кнопке «?»." },
];

export default function Onboarding({ onDone }) {
  const [i, setI] = useState(0);
  const s = STEPS[i];
  return (
    <Modal open onClose={onDone}>
      <div className="p-8 text-center">
        <div className="w-16 h-16 mx-auto rounded-2xl flex items-center justify-center mb-5 animate-pop" key={i} style={{ background: "linear-gradient(135deg, var(--color-accent), var(--color-pink))" }}><s.icon size={30} color="white" /></div>
        <h2 className="text-xl font-bold mb-3">{s.title}</h2>
        <p className="muted leading-relaxed mb-7">{s.text}</p>
        <div className="flex justify-center gap-1.5 mb-6">{STEPS.map((_, j) => <span key={j} className="h-1.5 rounded-full transition-all" style={{ width: j === i ? 24 : 8, background: j === i ? "var(--color-accent)" : "var(--line)" }} />)}</div>
        <div className="flex gap-2 justify-center">
          <button className="btn-ghost" onClick={onDone}>Пропустить</button>
          <button className="btn-primary" onClick={() => (i < STEPS.length - 1 ? setI(i + 1) : onDone())}>{i < STEPS.length - 1 ? <>Далее<ArrowRight size={15} /></> : "Начать"}</button>
        </div>
      </div>
    </Modal>
  );
}
