import { CatalogoComposicoes } from "./Catalogo";
import { MyComposition } from "./Composition";

export const RemotionRoot: React.FC = () => {
  return (
    <>
      <MyComposition />
      <CatalogoComposicoes />
    </>
  );
};
