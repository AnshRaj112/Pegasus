import { Skeleton } from 'antd';
import { useAppSelector } from '~/redux/store';
import styles from '../Test.module.scss';

const SavedView = () => {
  const { data, isFetching } = useAppSelector((state) => state.test.savedTests);

  if (isFetching) {
    return <div className="p-4"><Skeleton active paragraph={{ rows: 5 }} /></div>;
  }

  if (!data || data.length === 0) {
    return <div className="p-4 text-center text-muted">No saved tests found.</div>;
  }

  return (
    <div>
      {data.map((test) => (
        <div key={test.id} className={`d-flex justify-content-between align-items-center ${styles.listRow}`}>
          <div className="d-flex align-items-center col-6">
            <span className="me-2 text-secondary">⊟</span>
            {test.isDraft && <span className="badge bg-light text-dark border me-2">Draft</span>}
            <div>
              <div className="fw-bold">{test.title}</div>
              <div className="text-muted small">{test.subtitle}</div>
            </div>
          </div>
          
          <div className="col-6 text-muted small">
            {test.schedule}
          </div>
        </div>
      ))}
    </div>
  );
};

export default SavedView;