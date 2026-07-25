declare module "plotly.js-basic-dist-min" {
  type PlotlyValue = string | number | boolean | null | PlotlyValue[] | {
    [key: string]: PlotlyValue;
  };

  type PlotlyObject = Record<string, PlotlyValue>;

  const Plotly: {
    react(
      element: HTMLElement,
      data: PlotlyObject[],
      layout?: PlotlyObject,
      config?: PlotlyObject,
    ): Promise<void>;
    purge(element: HTMLElement): void;
  };

  export default Plotly;
}

