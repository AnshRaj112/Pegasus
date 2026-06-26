export interface AsyncState<T> {
  data: T | null;
  isFetching: boolean;
  error: string | null;
}

export interface TestEntity {
  id: string;
  title: string;
  subtitle: string;
  schedule: string;
  type: 'F' | 'L' | 'F+' | string; 
  status?: 'Completed' | 'Incoherent' | 'Ended';
  result?: 'Pass' | 'Fail';
  duration?: string;
  endedDate?: string;
  endedTime?: string;
  nextRun?: string;
  isDraft?: boolean;
}

export interface TestResponse {
  active: TestEntity[];
  completed: TestEntity[];
  saved: TestEntity[];
}

export interface TestReducerState {
  activeTests: AsyncState<TestEntity[]>;
  completedTests: AsyncState<TestEntity[]>;
  savedTests: AsyncState<TestEntity[]>;
}