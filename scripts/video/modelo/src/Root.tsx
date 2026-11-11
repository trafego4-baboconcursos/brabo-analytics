import { CatalogoComposicoes } from "./Catalogo";
import { CriativoComposicoes } from "./Criativo";

export const RemotionRoot: React.FC = () => {
  return (
    <>
      <CriativoComposicoes />
      <CatalogoComposicoes />
    </>
  );
};
